(function(){
"use strict";

/* =====================================================================
   Minecraft NBT — universal engine
   Encodings:
     java            big-endian, named root            (Vanilla/Paper/Spigot/Fabric/Forge)
     java-network    big-endian, nameless root         (Java 1.20.2+ protocol)
     bedrock-level   little-endian + 8-byte header     (Bedrock level.dat, BDS/PMMP/Nukkit)
     bedrock         little-endian, named root         (.mcstructure, LevelDB values)
     bedrock-network little-endian varint, named root  (Bedrock protocol)
   Compression: none | gzip | zlib
   ===================================================================== */

/* UI strings — the page injects a localized table as window.__NBT_STRINGS__ */
const STR=(typeof window!=="undefined"&&window.__NBT_STRINGS__)||{};
function t(key,fallback){
  const tpl=STR[key]||fallback;
  const args=Array.prototype.slice.call(arguments,2);
  return String(tpl).replace(/\{(\d+)\}/g,function(m,i){
    return args[i]===undefined?m:args[i];
  });
}

const TAG={END:0,BYTE:1,SHORT:2,INT:3,LONG:4,FLOAT:5,DOUBLE:6,BYTE_ARRAY:7,STRING:8,LIST:9,COMPOUND:10,INT_ARRAY:11,LONG_ARRAY:12};
const TAG_NAMES={0:"End",1:"Byte",2:"Short",3:"Int",4:"Long",5:"Float",6:"Double",7:"Byte[]",8:"String",9:"List",10:"Compound",11:"Int[]",12:"Long[]"};
const TAG_SNBT_SUFFIX={1:"b",2:"s",3:"",4:"L",5:"f",6:"d"};
const PLATFORM_LE=new Uint8Array(new Uint32Array([1]).buffer)[0]===1;

const FORMATS={
  "java":{le:false,varint:false,rootless:false,header:false,edition:"java",label:"Java big-endian"},
  "java-network":{le:false,varint:false,rootless:true,header:false,edition:"java",label:"Java network (nameless root)"},
  "bedrock-level":{le:true,varint:false,rootless:false,header:true,edition:"bedrock",label:"Bedrock level.dat (8-byte header)"},
  "bedrock":{le:true,varint:false,rootless:false,header:false,edition:"bedrock",label:"Bedrock little-endian"},
  "bedrock-network":{le:true,varint:true,rootless:false,header:false,edition:"bedrock",label:"Bedrock network (varint)"}
};
/* probe order: most specific first */
const PROBE_ORDER=["bedrock-level","java","bedrock","bedrock-network","java-network"];

/* ===== STRING CODEC =====
   Java writes modified UTF-8 (CESU-8: astral chars as two 3-byte halves, NUL as C0 80).
   Bedrock writes standard UTF-8. The decoder accepts both; the encoder picks per format. */
const utf8Decoder=new TextDecoder("utf-8");
const utf8Encoder=new TextEncoder();

function decodeString(bytes){
  let ascii=true;
  for(let i=0;i<bytes.length;i++){if(bytes[i]>=0x80){ascii=false;break}}
  if(ascii)return utf8Decoder.decode(bytes);
  let out="",i=0;
  const n=bytes.length;
  while(i<n){
    const b=bytes[i];
    if(b<0x80){out+=String.fromCharCode(b);i+=1}
    else if((b&0xe0)===0xc0){
      if(i+1>=n)break;
      out+=String.fromCharCode(((b&0x1f)<<6)|(bytes[i+1]&0x3f));i+=2;
    }else if((b&0xf0)===0xe0){
      if(i+2>=n)break;
      out+=String.fromCharCode(((b&0x0f)<<12)|((bytes[i+1]&0x3f)<<6)|(bytes[i+2]&0x3f));i+=3;
    }else if((b&0xf8)===0xf0){
      if(i+3>=n)break;
      const cp=((b&0x07)<<18)|((bytes[i+1]&0x3f)<<12)|((bytes[i+2]&0x3f)<<6)|(bytes[i+3]&0x3f);
      out+=String.fromCodePoint(cp);i+=4;
    }else{out+="�";i+=1}
  }
  return out;
}

/* standard UTF-8 (Bedrock) */
function encodeStringUTF8(s){return utf8Encoder.encode(s)}

/* modified UTF-8 / CESU-8 (Java) */
function encodeStringMUTF8(s){
  let len=0;
  for(let i=0;i<s.length;i++){
    const c=s.charCodeAt(i);
    if(c>=0x0001&&c<=0x007f)len+=1;
    else if(c<=0x07ff)len+=2;
    else len+=3;
  }
  const out=new Uint8Array(len);
  let p=0;
  for(let i=0;i<s.length;i++){
    const c=s.charCodeAt(i);
    if(c>=0x0001&&c<=0x007f)out[p++]=c;
    else if(c<=0x07ff){out[p++]=0xc0|(c>>6);out[p++]=0x80|(c&0x3f)}
    else{out[p++]=0xe0|(c>>12);out[p++]=0x80|((c>>6)&0x3f);out[p++]=0x80|(c&0x3f)}
  }
  return out;
}

/* ===== COMPRESSION ===== */
function sniffCompression(bytes){
  if(bytes.length>=2&&bytes[0]===0x1f&&bytes[1]===0x8b)return "gzip";
  if(bytes.length>=2&&(bytes[0]&0x0f)===0x08&&(((bytes[0]<<8)|bytes[1])%31)===0)return "zlib";
  return "none";
}
function streamsSupported(){return typeof DecompressionStream!=="undefined"&&typeof CompressionStream!=="undefined"}

async function runStream(bytes,stream){
  const blob=new Blob([bytes]);
  const out=blob.stream().pipeThrough(stream);
  const chunks=[];let total=0;
  const reader=out.getReader();
  for(;;){
    const r=await reader.read();
    if(r.done)break;
    chunks.push(r.value);total+=r.value.length;
  }
  const res=new Uint8Array(total);
  let off=0;
  for(const c of chunks){res.set(c,off);off+=c.length}
  return res;
}
async function decompressBytes(bytes,kind){
  if(kind==="none")return bytes;
  if(!streamsSupported())throw new Error("This browser cannot decompress "+kind+" (Compression Streams API missing)");
  return runStream(bytes,new DecompressionStream(kind==="gzip"?"gzip":"deflate"));
}
async function compressBytes(bytes,kind){
  if(kind==="none")return bytes;
  if(!streamsSupported())throw new Error("This browser cannot compress "+kind+" (Compression Streams API missing)");
  return runStream(bytes,new CompressionStream(kind==="gzip"?"gzip":"deflate"));
}

/* ===== READER ===== */
class NBTReader{
  constructor(bytes,opts){
    this.bytes=bytes;
    this.view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
    this.off=0;
    this.le=!!opts.le;
    this.varint=!!opts.varint;
    this.nodes=0;
    this.maxNodes=opts.maxNodes||8000000;
  }
  need(n){
    if(n<0||this.off+n>this.bytes.length)throw new Error("Unexpected end of data at offset "+this.off);
  }
  tick(){if(++this.nodes>this.maxNodes)throw new Error("Tag count limit exceeded")}
  readByte(){this.need(1);return this.view.getInt8(this.off++)}
  readUByte(){this.need(1);return this.view.getUint8(this.off++)}
  readShort(){this.need(2);const v=this.view.getInt16(this.off,this.le);this.off+=2;return v}
  readUShort(){this.need(2);const v=this.view.getUint16(this.off,this.le);this.off+=2;return v}
  readRawInt(){this.need(4);const v=this.view.getInt32(this.off,this.le);this.off+=4;return v}
  readRawLong(){this.need(8);const v=this.view.getBigInt64(this.off,this.le);this.off+=8;return v}
  readUVarInt(){
    let result=0,shift=0;
    for(let i=0;i<5;i++){
      this.need(1);
      const b=this.bytes[this.off++];
      result|=(b&0x7f)<<shift;
      if((b&0x80)===0)return result>>>0;
      shift+=7;
    }
    throw new Error("VarInt too long");
  }
  readVarInt(){
    const raw=this.readUVarInt();
    return (raw>>>1)^-(raw&1);
  }
  readUVarLong(){
    let result=0n,shift=0n;
    for(let i=0;i<10;i++){
      this.need(1);
      const b=BigInt(this.bytes[this.off++]);
      result|=(b&0x7fn)<<shift;
      if((b&0x80n)===0n)return BigInt.asUintN(64,result);
      shift+=7n;
    }
    throw new Error("VarLong too long");
  }
  readVarLong(){
    const raw=this.readUVarLong();
    return BigInt.asIntN(64,(raw>>1n)^-(raw&1n));
  }
  readInt(){return this.varint?this.readVarInt():this.readRawInt()}
  readLong(){return this.varint?this.readVarLong():this.readRawLong()}
  readFloat(){this.need(4);const v=this.view.getFloat32(this.off,this.le);this.off+=4;return v}
  readDouble(){this.need(8);const v=this.view.getFloat64(this.off,this.le);this.off+=8;return v}
  readString(){
    const len=this.varint?this.readUVarInt():this.readUShort();
    this.need(len);
    const slice=this.bytes.subarray(this.off,this.off+len);
    this.off+=len;
    return decodeString(slice);
  }
  readLength(elemSize){
    const len=this.readInt();
    if(len<0)throw new Error("Negative array length: "+len);
    if(len*elemSize>this.bytes.length-this.off)throw new Error("Array length "+len+" exceeds remaining data");
    return len;
  }
  readByteArray(){
    const len=this.readLength(1);
    const arr=new Int8Array(this.bytes.buffer.slice(this.bytes.byteOffset+this.off,this.bytes.byteOffset+this.off+len));
    this.off+=len;
    return arr;
  }
  readIntArray(){
    const len=this.readLength(4);
    let arr;
    if(!this.varint&&this.le===PLATFORM_LE){
      arr=new Int32Array(this.bytes.buffer.slice(this.bytes.byteOffset+this.off,this.bytes.byteOffset+this.off+len*4));
      this.off+=len*4;
    }else{
      arr=new Int32Array(len);
      for(let i=0;i<len;i++)arr[i]=this.readInt();
    }
    return arr;
  }
  readLongArray(){
    const len=this.readLength(8);
    let arr;
    if(!this.varint&&this.le===PLATFORM_LE){
      arr=new BigInt64Array(this.bytes.buffer.slice(this.bytes.byteOffset+this.off,this.bytes.byteOffset+this.off+len*8));
      this.off+=len*8;
    }else{
      arr=new BigInt64Array(len);
      for(let i=0;i<len;i++)arr[i]=this.readLong();
    }
    return arr;
  }
  readTag(type){
    this.tick();
    switch(type){
      case TAG.BYTE:return{type:type,value:this.readByte()};
      case TAG.SHORT:return{type:type,value:this.readShort()};
      case TAG.INT:return{type:type,value:this.readInt()};
      case TAG.LONG:return{type:type,value:this.readLong()};
      case TAG.FLOAT:return{type:type,value:this.readFloat()};
      case TAG.DOUBLE:return{type:type,value:this.readDouble()};
      case TAG.BYTE_ARRAY:return{type:type,value:this.readByteArray()};
      case TAG.STRING:return{type:type,value:this.readString()};
      case TAG.LIST:{
        const listType=this.readUByte();
        const len=this.readInt();
        if(len<0)throw new Error("Negative list length");
        if(listType===TAG.END&&len>0)throw new Error("List of TAG_End with "+len+" entries");
        if(listType>12)throw new Error("Unknown list element type: "+listType);
        const items=new Array(len);
        for(let i=0;i<len;i++)items[i]=this.readTag(listType);
        return{type:type,listType:listType,value:items};
      }
      case TAG.COMPOUND:{
        const entries=[];
        for(;;){
          const t=this.readUByte();
          if(t===TAG.END)break;
          if(t>12)throw new Error("Unknown tag type: "+t);
          const name=this.readString();
          const tag=this.readTag(t);
          tag.name=name;
          entries.push(tag);
        }
        return{type:type,value:entries};
      }
      case TAG.INT_ARRAY:return{type:type,value:this.readIntArray()};
      case TAG.LONG_ARRAY:return{type:type,value:this.readLongArray()};
      default:throw new Error("Unknown tag type: "+type);
    }
  }
  parseRoot(rootless){
    const rootType=this.readUByte();
    if(rootType!==TAG.COMPOUND)throw new Error("Root tag must be TAG_Compound, got "+rootType);
    const name=rootless?"":this.readString();
    const root=this.readTag(TAG.COMPOUND);
    root.name=name;
    return root;
  }
}

/* ===== WRITER ===== */
class NBTWriter{
  constructor(opts){
    this.le=!!opts.le;
    this.varint=!!opts.varint;
    this.mutf8=!!opts.mutf8;
    this.buf=new Uint8Array(65536);
    this.view=new DataView(this.buf.buffer);
    this.off=0;
  }
  ensure(n){
    if(this.off+n<=this.buf.length)return;
    let cap=this.buf.length*2;
    while(cap<this.off+n)cap*=2;
    const nb=new Uint8Array(cap);
    nb.set(this.buf.subarray(0,this.off));
    this.buf=nb;
    this.view=new DataView(nb.buffer);
  }
  writeByte(v){this.ensure(1);this.view.setInt8(this.off++,v)}
  writeUByte(v){this.ensure(1);this.buf[this.off++]=v&0xff}
  writeShort(v){this.ensure(2);this.view.setInt16(this.off,v,this.le);this.off+=2}
  writeUShort(v){this.ensure(2);this.view.setUint16(this.off,v,this.le);this.off+=2}
  writeRawInt(v){this.ensure(4);this.view.setInt32(this.off,v,this.le);this.off+=4}
  writeRawLong(v){this.ensure(8);this.view.setBigInt64(this.off,BigInt(v),this.le);this.off+=8}
  writeUVarInt(v){
    let x=v>>>0;
    this.ensure(5);
    for(;;){
      if((x&~0x7f)===0){this.buf[this.off++]=x;return}
      this.buf[this.off++]=(x&0x7f)|0x80;
      x>>>=7;
    }
  }
  writeVarInt(v){this.writeUVarInt(((v<<1)^(v>>31))>>>0)}
  writeUVarLong(v){
    let x=BigInt.asUintN(64,BigInt(v));
    this.ensure(10);
    for(;;){
      if((x&~0x7fn)===0n){this.buf[this.off++]=Number(x);return}
      this.buf[this.off++]=Number(x&0x7fn)|0x80;
      x>>=7n;
    }
  }
  writeVarLong(v){
    const b=BigInt.asIntN(64,BigInt(v));
    this.writeUVarLong(BigInt.asUintN(64,(b<<1n)^(b>>63n)));
  }
  writeInt(v){this.varint?this.writeVarInt(v|0):this.writeRawInt(v)}
  writeLong(v){this.varint?this.writeVarLong(v):this.writeRawLong(v)}
  writeFloat(v){this.ensure(4);this.view.setFloat32(this.off,v,this.le);this.off+=4}
  writeDouble(v){this.ensure(8);this.view.setFloat64(this.off,v,this.le);this.off+=8}
  writeString(s){
    const bytes=this.mutf8?encodeStringMUTF8(s):encodeStringUTF8(s);
    if(this.varint)this.writeUVarInt(bytes.length);
    else{
      if(bytes.length>65535)throw new Error("String too long for this format: "+bytes.length+" bytes");
      this.writeUShort(bytes.length);
    }
    this.ensure(bytes.length);
    this.buf.set(bytes,this.off);
    this.off+=bytes.length;
  }
  writeTag(tag){
    switch(tag.type){
      case TAG.BYTE:this.writeByte(tag.value);break;
      case TAG.SHORT:this.writeShort(tag.value);break;
      case TAG.INT:this.writeInt(tag.value);break;
      case TAG.LONG:this.writeLong(tag.value);break;
      case TAG.FLOAT:this.writeFloat(tag.value);break;
      case TAG.DOUBLE:this.writeDouble(tag.value);break;
      case TAG.BYTE_ARRAY:{
        const a=tag.value;
        this.writeInt(a.length);
        this.ensure(a.length);
        this.buf.set(new Uint8Array(a.buffer,a.byteOffset,a.length),this.off);
        this.off+=a.length;
        break;
      }
      case TAG.STRING:this.writeString(tag.value);break;
      case TAG.LIST:{
        const items=tag.value;
        const lt=items.length?items[0].type:(tag.listType||TAG.END);
        this.writeUByte(lt);
        this.writeInt(items.length);
        for(let i=0;i<items.length;i++)this.writeTag(items[i]);
        break;
      }
      case TAG.COMPOUND:{
        const entries=tag.value;
        for(let i=0;i<entries.length;i++){
          this.writeUByte(entries[i].type);
          this.writeString(entries[i].name||"");
          this.writeTag(entries[i]);
        }
        this.writeUByte(TAG.END);
        break;
      }
      case TAG.INT_ARRAY:{
        const a=tag.value;
        this.writeInt(a.length);
        if(!this.varint&&this.le===PLATFORM_LE){
          this.ensure(a.length*4);
          this.buf.set(new Uint8Array(a.buffer,a.byteOffset,a.length*4),this.off);
          this.off+=a.length*4;
        }else{
          for(let i=0;i<a.length;i++)this.writeInt(a[i]);
        }
        break;
      }
      case TAG.LONG_ARRAY:{
        const a=tag.value;
        this.writeInt(a.length);
        if(!this.varint&&this.le===PLATFORM_LE){
          this.ensure(a.length*8);
          this.buf.set(new Uint8Array(a.buffer,a.byteOffset,a.length*8),this.off);
          this.off+=a.length*8;
        }else{
          for(let i=0;i<a.length;i++)this.writeLong(a[i]);
        }
        break;
      }
      default:throw new Error("Cannot write tag type "+tag.type);
    }
  }
  writeRoot(root,rootless){
    this.writeUByte(TAG.COMPOUND);
    if(!rootless)this.writeString(root.name||"");
    this.writeTag(root);
  }
  bytes(){return this.buf.subarray(0,this.off)}
}

/* ===== SERIALIZE / PARSE FRONT-ENDS ===== */
function parseWithFormat(bytes,formatId){
  const f=FORMATS[formatId];
  let payload=bytes,headerVersion=null;
  if(f.header){
    if(bytes.length<8)throw new Error("Too short for a header");
    const hv=new DataView(bytes.buffer,bytes.byteOffset,8);
    headerVersion=hv.getInt32(0,true);
    const declared=hv.getUint32(4,true);
    if(headerVersion<0||headerVersion>1000)throw new Error("Implausible storage version: "+headerVersion);
    if(declared!==bytes.length-8&&declared>bytes.length-8)throw new Error("Header length "+declared+" exceeds payload");
    payload=bytes.subarray(8);
  }
  const reader=new NBTReader(payload,{le:f.le,varint:f.varint});
  const root=reader.parseRoot(f.rootless);
  return{root:root,headerVersion:headerVersion,consumed:reader.off,total:payload.length};
}

function detectFormat(bytes){
  let best=null;
  for(const id of PROBE_ORDER){
    try{
      const r=parseWithFormat(bytes,id);
      const score=r.consumed/Math.max(1,r.total);
      if(r.consumed===r.total)return{formatId:id,result:r,exact:true};
      if(!best||score>best.score)best={formatId:id,result:r,score:score,exact:false};
    }catch(e){/* not this format */}
  }
  if(best&&best.score>=0.5)return best;
  throw new Error("Not a recognizable NBT file (tried Java, Bedrock, network and header variants)");
}

function serialize(root,formatId,headerVersion){
  const f=FORMATS[formatId];
  const w=new NBTWriter({le:f.le,varint:f.varint,mutf8:f.edition==="java"});
  w.writeRoot(root,f.rootless);
  const nbt=w.bytes();
  if(!f.header)return nbt.slice();
  const out=new Uint8Array(8+nbt.length);
  const dv=new DataView(out.buffer);
  dv.setInt32(0,headerVersion==null?8:headerVersion,true);
  dv.setUint32(4,nbt.length,true);
  out.set(nbt,8);
  return out;
}

/* ===== SNBT ===== */
const SNBT_BARE=/^[A-Za-z0-9._+-]+$/;
function snbtString(s){
  return '"'+s.replace(/\\/g,"\\\\").replace(/"/g,'\\"')+'"';
}
function snbtKey(k){return SNBT_BARE.test(k)?k:snbtString(k)}
function toSNBT(tag,indent){
  const pad=indent==null?"":indent;
  const nl=indent==null?"":"\n";
  const step=indent==null?"":"  ";
  function walk(t,depth){
    const cur=indent==null?"":pad+step.repeat(depth);
    const inner=indent==null?"":pad+step.repeat(depth+1);
    switch(t.type){
      case TAG.BYTE:case TAG.SHORT:case TAG.INT:case TAG.LONG:
        return String(t.value)+TAG_SNBT_SUFFIX[t.type];
      case TAG.FLOAT:case TAG.DOUBLE:{
        let s=String(t.value);
        if(!/[.eE]/.test(s))s+=".0";
        return s+TAG_SNBT_SUFFIX[t.type];
      }
      case TAG.STRING:return snbtString(t.value);
      case TAG.BYTE_ARRAY:return "[B;"+Array.prototype.join.call(t.value,"b,")+(t.value.length?"b":"")+"]";
      case TAG.INT_ARRAY:return "[I;"+Array.prototype.join.call(t.value,",")+"]";
      case TAG.LONG_ARRAY:return "[L;"+Array.prototype.join.call(t.value,"L,")+(t.value.length?"L":"")+"]";
      case TAG.LIST:{
        if(!t.value.length)return "[]";
        const parts=t.value.map(function(c){return inner+walk(c,depth+1)});
        return "["+nl+parts.join(","+nl)+nl+cur+"]";
      }
      case TAG.COMPOUND:{
        if(!t.value.length)return "{}";
        const parts=t.value.map(function(c){return inner+snbtKey(c.name||"")+":"+walk(c,depth+1)});
        return "{"+nl+parts.join(","+nl)+nl+cur+"}";
      }
      default:return "";
    }
  }
  return walk(tag,0);
}

/* ===== STATE ===== */
let currentRoot=null;
let srcFormat="bedrock-level";
let srcCompression="none";
let headerVersion=8;
let fileName="level.dat";
let fileSize=0;
let addTargetTag=null;
let addTargetWrapper=null;
let arrayTargetTag=null;
let arrayTargetEl=null;
let rootWrapper=null;

const PAGE_SIZE=200;
const ARRAY_TEXT_LIMIT=100000;

/* ===== DOM REFS ===== */
const dropZone=document.getElementById("dropZone");
const fileInput=document.getElementById("fileInput");
const editorArea=document.getElementById("editorArea");
const fileInfo=document.getElementById("fileInfo");
const treeRoot=document.getElementById("treeRoot");
const bottomBar=document.getElementById("bottomBar");
const toastContainer=document.getElementById("toastContainer");
const addTagModal=document.getElementById("addTagModal");
const arrayModal=document.getElementById("arrayModal");
const contentSections=document.getElementById("contentSections");
const outFormat=document.getElementById("outFormat");
const outCompression=document.getElementById("outCompression");
const searchInput=document.getElementById("searchInput");
const searchResults=document.getElementById("searchResults");

/* ===== TOAST ===== */
function toast(msg,type){
  const el=document.createElement("div");
  el.className="toast "+(type||"info");
  el.textContent=msg;
  toastContainer.appendChild(el);
  setTimeout(function(){
    el.style.opacity="0";el.style.transition="opacity .3s";
    setTimeout(function(){el.remove()},300);
  },3400);
}
function escHtml(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
function formatBytes(n){
  if(n<1024)return n+" B";
  if(n<1024*1024)return (n/1024).toFixed(1)+" KB";
  return (n/1048576).toFixed(2)+" MB";
}

/* ===== FILE LOADING ===== */
function loadFile(file){
  fileName=file.name||"data.nbt";
  fileSize=file.size;
  const reader=new FileReader();
  reader.onerror=function(){toast(t("readfail","Could not read the file"),"error")};
  reader.onload=function(e){
    openBuffer(new Uint8Array(e.target.result));
  };
  reader.readAsArrayBuffer(file);
}

async function openBuffer(raw){
  try{
    if(raw.length<4)throw new Error("File is too small to contain NBT data");
    srcCompression=sniffCompression(raw);
    const bytes=await decompressBytes(raw,srcCompression);
    const det=detectFormat(bytes);
    srcFormat=det.formatId;
    headerVersion=det.result.headerVersion==null?8:det.result.headerVersion;
    currentRoot=det.result.root;
    outFormat.value=srcFormat;
    outCompression.value=srcCompression;
    showEditor();
    const trailing=det.result.total-det.result.consumed;
    toast(t("loaded","Loaded as {0}",FORMATS[srcFormat].label+(srcCompression!=="none"?" / "+srcCompression:"")),"success");
    if(trailing>0)toast(t("trailing","{0} trailing byte(s) after the root tag were ignored",trailing),"info");
  }catch(err){
    console.error(err);
    toast(t("error","Error: {0}",err.message),"error");
  }
}

/* ===== EDITOR SHELL ===== */
function showEditor(){
  editorArea.classList.add("visible");
  bottomBar.classList.add("visible");
  contentSections.classList.add("hidden");
  renderFileInfo();
  renderTree();
  const jump=findTagPath(function(t){return t.name==="LevelName"&&t.type===TAG.STRING});
  if(jump){
    const btn=document.createElement("button");
    btn.className="ln-jump";
    btn.type="button";
    btn.textContent=t("editlevelname","✎ Edit LevelName");
    btn.addEventListener("click",function(){revealPath(jump,true)});
    fileInfo.appendChild(btn);
    setTimeout(function(){revealPath(jump,true)},80);
  }
}

function renderFileInfo(){
  const f=FORMATS[srcFormat];
  fileInfo.innerHTML=
    '<span class="fmt-badge '+f.edition+'">'+(f.edition==="java"?"Java":"Bedrock")+'</span>'+
    '<span class="fname">'+escHtml(fileName)+'</span>'+
    '<span class="fmeta">'+escHtml(f.label)+
    (srcCompression!=="none"?" &middot; "+srcCompression:" &middot; "+t("uncompressed","uncompressed"))+
    (f.header?" &middot; "+t("storage","storage v{0}",headerVersion):"")+
    " &middot; "+formatBytes(fileSize)+'</span>';
}

function closeEditor(){
  currentRoot=null;
  rootWrapper=null;
  editorArea.classList.remove("visible");
  bottomBar.classList.remove("visible");
  contentSections.classList.remove("hidden");
  treeRoot.innerHTML="";
  searchResults.classList.remove("visible");
  searchResults.innerHTML="";
  searchInput.value="";
  fileInput.value="";
}

/* ===== VALUE HELPERS ===== */
function isContainer(tag){return tag.type===TAG.COMPOUND||tag.type===TAG.LIST}
function isArrayTag(tag){return tag.type===TAG.BYTE_ARRAY||tag.type===TAG.INT_ARRAY||tag.type===TAG.LONG_ARRAY}
function isEditable(tag){return!isContainer(tag)&&!isArrayTag(tag)}
function arrayElemType(tag){
  return tag.type===TAG.BYTE_ARRAY?TAG.BYTE:(tag.type===TAG.INT_ARRAY?TAG.INT:TAG.LONG);
}
function childCount(tag){
  if(isContainer(tag)||isArrayTag(tag))return tag.value.length;
  return 0;
}
function formatValue(tag){
  switch(tag.type){
    case TAG.BYTE:case TAG.SHORT:case TAG.INT:case TAG.LONG:case TAG.FLOAT:case TAG.DOUBLE:
      return String(tag.value);
    case TAG.STRING:return '"'+tag.value+'"';
    case TAG.BYTE_ARRAY:return "["+tag.value.length+" bytes]";
    case TAG.INT_ARRAY:return "["+tag.value.length+" ints]";
    case TAG.LONG_ARRAY:return "["+tag.value.length+" longs]";
    case TAG.LIST:return tag.value.length+" "+(tag.value.length===1?"entry":"entries")+
      (tag.value.length?" of "+(TAG_NAMES[tag.listType]||"?"):"");
    case TAG.COMPOUND:return tag.value.length+" "+(tag.value.length===1?"entry":"entries");
    default:return "";
  }
}
function applyValue(tag,str){
  switch(tag.type){
    case TAG.BYTE:{const n=parseInt(str,10);if(isNaN(n)||n<-128||n>255)throw new Error("Byte must be -128..127");tag.value=n>127?n-256:n;break}
    case TAG.SHORT:{const n=parseInt(str,10);if(isNaN(n)||n<-32768||n>32767)throw new Error("Short must be -32768..32767");tag.value=n;break}
    case TAG.INT:{const n=parseInt(str,10);if(isNaN(n)||n<-2147483648||n>2147483647)throw new Error("Int must be -2147483648..2147483647");tag.value=n;break}
    case TAG.LONG:{const b=BigInt(str.trim());if(b<-(2n**63n)||b>2n**63n-1n)throw new Error("Long out of 64-bit range");tag.value=b;break}
    case TAG.FLOAT:{const n=parseFloat(str);if(isNaN(n))throw new Error("Invalid float");tag.value=Math.fround(n);break}
    case TAG.DOUBLE:{const n=parseFloat(str);if(isNaN(n))throw new Error("Invalid double");tag.value=n;break}
    case TAG.STRING:tag.value=str;break;
    default:throw new Error("This tag type is not editable inline");
  }
}
function parseArrayText(type,text){
  const parts=text.split(/[,\s]+/).map(function(s){return s.trim()}).filter(function(s){return s!==""});
  if(type===TAG.BYTE_ARRAY){
    const a=new Int8Array(parts.length);
    for(let i=0;i<parts.length;i++){
      const n=parseInt(parts[i],10);
      if(isNaN(n)||n<-128||n>255)throw new Error("Invalid byte: "+parts[i]);
      a[i]=n;
    }
    return a;
  }
  if(type===TAG.INT_ARRAY){
    const a=new Int32Array(parts.length);
    for(let i=0;i<parts.length;i++){
      const n=parseInt(parts[i],10);
      if(isNaN(n))throw new Error("Invalid int: "+parts[i]);
      a[i]=n;
    }
    return a;
  }
  const a=new BigInt64Array(parts.length);
  for(let i=0;i<parts.length;i++)a[i]=BigInt(parts[i].replace(/[lL]$/,""));
  return a;
}
function typedArrayWithout(arr,index){
  const Ctor=arr.constructor;
  const out=new Ctor(arr.length-1);
  out.set(arr.subarray(0,index),0);
  out.set(arr.subarray(index+1),index);
  return out;
}
function typedArrayAppend(arr,value){
  const Ctor=arr.constructor;
  const out=new Ctor(arr.length+1);
  out.set(arr,0);
  out[arr.length]=value;
  return out;
}

/* ===== TREE (lazy + paged) ===== */
function renderTree(){
  treeRoot.innerHTML="";
  if(!currentRoot)return;
  rootWrapper=makeNode(currentRoot,null,null,null);
  treeRoot.appendChild(rootWrapper);
  rootWrapper._expand();
}

function makeNode(tag,parentTag,index,parentWrapper){
  const wrapper=document.createElement("div");
  wrapper.className="tree-node";
  wrapper._tag=tag;
  wrapper._parentWrapper=parentWrapper;

  const row=document.createElement("div");
  row.className="node-row";
  wrapper._row=row;

  const expandable=isContainer(tag)||isArrayTag(tag);

  const toggle=document.createElement("button");
  toggle.className="node-toggle"+(expandable?"":" leaf");
  toggle.textContent="▶";
  toggle.type="button";
  toggle.setAttribute("aria-label","Toggle");
  row.appendChild(toggle);

  const badge=document.createElement("span");
  badge.className="tag-badge";
  badge.dataset.t=tag.type;
  badge.textContent=TAG_NAMES[tag.type]||"?";
  row.appendChild(badge);

  const nameEl=document.createElement("span");
  nameEl.className="node-name";
  if(tag.name!==undefined&&tag.name!==null&&tag.name!==""){
    nameEl.textContent=tag.name;
  }else if(index!==null){
    nameEl.textContent="["+index+"]";
    nameEl.style.color="var(--text2)";
  }else{
    nameEl.textContent=tag.name===""?"(root)":"";
    nameEl.style.color="var(--text2)";
  }
  row.appendChild(nameEl);

  const valEl=document.createElement("span");
  valEl.className="node-value";
  valEl.textContent=formatValue(tag);
  row.appendChild(valEl);

  if(isEditable(tag)){
    valEl.addEventListener("click",function(e){e.stopPropagation();startEditing(tag,valEl)});
  }else if(isArrayTag(tag)){
    valEl.addEventListener("click",function(e){e.stopPropagation();openArrayModal(tag,valEl)});
  }else{
    valEl.classList.add("ro");
  }

  const actions=document.createElement("span");
  actions.className="node-actions";
  if(isContainer(tag)){
    const addBtn=document.createElement("button");
    addBtn.type="button";
    addBtn.textContent="+";
    addBtn.title="Add child tag";
    addBtn.addEventListener("click",function(e){e.stopPropagation();openAddTagModal(tag,wrapper)});
    actions.appendChild(addBtn);
  }
  if(parentTag){
    const delBtn=document.createElement("button");
    delBtn.type="button";
    delBtn.className="del";
    delBtn.textContent="×";
    delBtn.title="Remove tag";
    delBtn.addEventListener("click",function(e){e.stopPropagation();removeChild(parentTag,index,parentWrapper)});
    actions.appendChild(delBtn);
  }
  row.appendChild(actions);
  wrapper.appendChild(row);

  if(!expandable){
    wrapper._expand=function(){};
    wrapper._rebuild=function(){return wrapper};
    return wrapper;
  }

  const children=document.createElement("div");
  children.className="node-children";
  wrapper.appendChild(children);

  const total=childCount(tag);
  const childEls=[];
  let shown=0,open=false;
  let loadMore=null;

  function childTagAt(i){
    if(isArrayTag(tag)){
      return{type:arrayElemType(tag),value:tag.value[i],__arr:tag,__idx:i};
    }
    return tag.value[i];
  }
  function buildPage(){
    const end=Math.min(total,shown+PAGE_SIZE);
    const frag=document.createDocumentFragment();
    for(let i=shown;i<end;i++){
      const el=makeNode(childTagAt(i),tag,i,wrapper);
      childEls.push(el);
      frag.appendChild(el);
    }
    shown=end;
    if(loadMore)children.insertBefore(frag,loadMore);
    else children.appendChild(frag);
    if(shown<total){
      if(!loadMore){
        loadMore=document.createElement("button");
        loadMore.type="button";
        loadMore.className="load-more";
        children.appendChild(loadMore);
        loadMore.addEventListener("click",function(e){e.stopPropagation();buildPage()});
      }
      loadMore.textContent=t("showmore","Show {0} more of {1} …",Math.min(PAGE_SIZE,total-shown),total);
    }else if(loadMore){
      loadMore.remove();loadMore=null;
    }
  }

  function setOpen(v){
    open=v;
    toggle.textContent=open?"▼":"▶";
    children.classList.toggle("open",open);
    if(open&&shown===0&&total>0)buildPage();
  }
  toggle.addEventListener("click",function(e){e.stopPropagation();setOpen(!open)});
  row.addEventListener("click",function(e){
    if(e.target===row||e.target===nameEl||e.target===badge)setOpen(!open);
  });

  wrapper._expand=function(){setOpen(true)};
  wrapper._isOpen=function(){return open};
  wrapper._ensureChild=function(i){
    if(i>=total)return null;
    setOpen(true);
    while(shown<=i&&shown<total)buildPage();
    return childEls[i];
  };
  wrapper._replaceChild=function(i,el){childEls[i]=el};
  wrapper._rebuild=function(){
    const fresh=makeNode(tag,parentTag,index,parentWrapper);
    wrapper.replaceWith(fresh);
    if(open)fresh._expand();
    if(parentWrapper&&parentWrapper._replaceChild&&index!==null)parentWrapper._replaceChild(index,fresh);
    if(!parentWrapper)rootWrapper=fresh;
    return fresh;
  };
  return wrapper;
}

/* ===== INLINE EDITING ===== */
function startEditing(tag,el){
  if(el.classList.contains("editing"))return;
  el.classList.add("editing");
  const original=tag.type===TAG.STRING?tag.value:String(tag.value);
  const input=document.createElement("input");
  input.type="text";
  input.value=original;
  input.autocapitalize="off";
  input.spellcheck=false;
  el.textContent="";
  el.appendChild(input);
  input.focus();
  input.select();
  let done=false;
  function finish(commit){
    if(done)return;
    done=true;
    el.classList.remove("editing");
    if(commit){
      try{
        applyValue(tag,input.value);
        if(tag.__arr)writeBackArrayElement(tag);
      }catch(err){
        toast(t("badvalue","Invalid value: {0}",err.message),"error");
      }
    }
    el.textContent=formatValue(tag);
  }
  input.addEventListener("blur",function(){finish(true)});
  input.addEventListener("keydown",function(e){
    if(e.key==="Enter"){e.preventDefault();finish(true);el.blur()}
    else if(e.key==="Escape"){e.preventDefault();finish(false)}
  });
}

function writeBackArrayElement(pseudo){
  const arr=pseudo.__arr.value;
  if(arr instanceof BigInt64Array)arr[pseudo.__idx]=BigInt(pseudo.value);
  else arr[pseudo.__idx]=pseudo.value;
  pseudo.value=arr[pseudo.__idx];
}

/* ===== ARRAY EDITING (modal) ===== */
function openArrayModal(tag,el){
  if(tag.value.length>ARRAY_TEXT_LIMIT){
    toast(t("arraytoobig","Array has {0} entries — expand it and edit elements individually",tag.value.length),"info");
    return;
  }
  arrayTargetTag=tag;
  arrayTargetEl=el;
  document.getElementById("arrayModalTitle").textContent=(TAG_NAMES[tag.type]||"Array")+" — "+t("entries","{0} entries",tag.value.length);
  document.getElementById("arrayModalText").value=Array.prototype.join.call(tag.value,", ");
  arrayModal.classList.add("visible");
}

/* ===== ADD / REMOVE ===== */
function removeChild(parentTag,index,parentWrapper){
  if(isArrayTag(parentTag)){
    parentTag.value=typedArrayWithout(parentTag.value,index);
  }else{
    parentTag.value.splice(index,1);
  }
  if(parentWrapper)parentWrapper._rebuild();
  else renderTree();
  toast(t("tagremoved","Tag removed"),"info");
}

function openAddTagModal(parentTag,wrapper){
  addTargetTag=parentTag;
  addTargetWrapper=wrapper;
  const nameInput=document.getElementById("newTagName");
  const typeSelect=document.getElementById("newTagType");
  const valueInput=document.getElementById("newTagValue");
  const listRow=document.getElementById("listSubtypeRow");
  nameInput.value="";
  valueInput.value="";
  const nameLabel=document.querySelector('label[for="newTagName"]');
  if(parentTag.type===TAG.LIST){
    nameInput.style.display="none";
    if(nameLabel)nameLabel.style.display="none";
    if(parentTag.value.length){
      typeSelect.value=String(parentTag.value[0].type);
      typeSelect.disabled=true;
    }else{
      typeSelect.value=String(parentTag.listType||TAG.STRING);
      typeSelect.disabled=false;
    }
  }else{
    nameInput.style.display="";
    if(nameLabel)nameLabel.style.display="";
    typeSelect.disabled=false;
    typeSelect.value=String(TAG.STRING);
  }
  listRow.style.display=(parseInt(typeSelect.value,10)===TAG.LIST)?"block":"none";
  addTagModal.classList.add("visible");
  if(parentTag.type!==TAG.LIST)setTimeout(function(){nameInput.focus()},50);
}

function createDefaultTag(type,valueStr,listSubtype){
  const v=(valueStr||"").trim();
  switch(type){
    case TAG.BYTE:case TAG.SHORT:case TAG.INT:case TAG.FLOAT:case TAG.DOUBLE:case TAG.STRING:{
      const tag={type:type,value:type===TAG.STRING?"":0};
      applyValue(tag,v===""?(type===TAG.STRING?"":"0"):v);
      return tag;
    }
    case TAG.LONG:return{type:type,value:v===""?0n:BigInt(v)};
    case TAG.BYTE_ARRAY:return{type:type,value:parseArrayText(TAG.BYTE_ARRAY,v)};
    case TAG.INT_ARRAY:return{type:type,value:parseArrayText(TAG.INT_ARRAY,v)};
    case TAG.LONG_ARRAY:return{type:type,value:parseArrayText(TAG.LONG_ARRAY,v)};
    case TAG.LIST:return{type:type,listType:listSubtype||TAG.COMPOUND,value:[]};
    case TAG.COMPOUND:return{type:type,value:[]};
    default:throw new Error("Unknown tag type");
  }
}

/* ===== SEARCH / NAVIGATION ===== */
function walkModel(visit,limitNodes){
  if(!currentRoot)return;
  const limit=limitNodes||400000;
  let seen=0;
  const stack=[{tag:currentRoot,path:[],label:currentRoot.name||"(root)"}];
  while(stack.length){
    const cur=stack.pop();
    if(++seen>limit)return;
    if(visit(cur.tag,cur.path,cur.label)===false)return;
    if(isContainer(cur.tag)){
      for(let i=cur.tag.value.length-1;i>=0;i--){
        const child=cur.tag.value[i];
        const label=cur.label+(cur.tag.type===TAG.LIST?"["+i+"]":"."+(child.name||"?"));
        stack.push({tag:child,path:cur.path.concat(i),label:label});
      }
    }
  }
}

function findTagPath(pred){
  let found=null;
  walkModel(function(tag,path){
    if(pred(tag)){found=path;return false}
  },100000);
  return found;
}

function revealPath(path,startEdit){
  if(!rootWrapper)return false;
  let w=rootWrapper;
  w._expand();
  for(let i=0;i<path.length;i++){
    const next=w._ensureChild?w._ensureChild(path[i]):null;
    if(!next)return false;
    w=next;
    if(i<path.length-1&&w._expand)w._expand();
  }
  const row=w._row;
  row.scrollIntoView({behavior:"smooth",block:"center"});
  /* only ever one highlighted row, otherwise stale jumps stay lit */
  const lit=treeRoot.querySelectorAll(".ln-flash");
  for(let i=0;i<lit.length;i++)lit[i].classList.remove("ln-flash");
  void row.offsetWidth;
  row.classList.add("ln-flash");
  if(startEdit){
    const valEl=row.querySelector(".node-value");
    if(valEl&&isEditable(w._tag))setTimeout(function(){startEditing(w._tag,valEl)},420);
  }
  return true;
}

function runSearch(){
  const q=searchInput.value.trim().toLowerCase();
  searchResults.innerHTML="";
  if(!q){searchResults.classList.remove("visible");return}
  const hits=[];
  walkModel(function(tag,path,label){
    if(!path.length)return;
    const name=(tag.name||"").toLowerCase();
    let match=name.indexOf(q)>=0;
    if(!match&&(tag.type===TAG.STRING))match=String(tag.value).toLowerCase().indexOf(q)>=0;
    if(!match&&tag.type>=TAG.BYTE&&tag.type<=TAG.DOUBLE)match=String(tag.value).toLowerCase().indexOf(q)>=0;
    if(match)hits.push({path:path,label:label,tag:tag});
    if(hits.length>=300)return false;
  });
  if(!hits.length){
    searchResults.innerHTML='<div class="sr-empty">'+escHtml(t("nomatch",'No tag matches "{0}"',searchInput.value))+'</div>';
    searchResults.classList.add("visible");
    return;
  }
  const frag=document.createDocumentFragment();
  hits.forEach(function(hit){
    const item=document.createElement("div");
    item.className="sr-item";
    item.innerHTML="<b>"+escHtml(hit.label)+"</b> &nbsp;"+escHtml(formatValue(hit.tag)).slice(0,120);
    item.addEventListener("click",function(){revealPath(hit.path,false)});
    frag.appendChild(item);
  });
  searchResults.appendChild(frag);
  searchResults.classList.add("visible");
  toast(t("matches","{0} match(es)",hits.length+(hits.length>=300?"+":"")),"info");
}

/* ===== SAVE ===== */
function downloadBytes(bytes,name,mime){
  const blob=new Blob([bytes],{type:mime||"application/octet-stream"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url;
  a.download=name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function(){URL.revokeObjectURL(url)},1000);
}

async function saveFile(){
  if(!currentRoot){toast(t("nofile","No file loaded"),"error");return}
  try{
    const fmt=outFormat.value;
    const comp=outCompression.value;
    const raw=serialize(currentRoot,fmt,headerVersion);
    const out=await compressBytes(raw,comp);
    downloadBytes(out,fileName);
    toast(t("saved","Saved {0} ({1}, {2})",fileName,formatBytes(out.length),
      FORMATS[fmt].label+(comp!=="none"?" / "+comp:"")),"success");
  }catch(err){
    console.error(err);
    toast(t("savefail","Save error: {0}",err.message),"error");
  }
}

function exportSNBT(){
  if(!currentRoot){toast(t("nofile","No file loaded"),"error");return}
  try{
    const text=toSNBT(currentRoot,"");
    const name=fileName.replace(/\.[^.]+$/,"")+".snbt";
    downloadBytes(utf8Encoder.encode(text),name,"text/plain");
    toast(t("exported","Exported {0}",name),"success");
  }catch(err){
    console.error(err);
    toast(t("snbtfail","SNBT error: {0}",err.message),"error");
  }
}

/* ===== EVENTS ===== */
dropZone.addEventListener("dragover",function(e){e.preventDefault();dropZone.classList.add("active")});
dropZone.addEventListener("dragleave",function(){dropZone.classList.remove("active")});
dropZone.addEventListener("drop",function(e){
  e.preventDefault();dropZone.classList.remove("active");
  if(e.dataTransfer.files.length)loadFile(e.dataTransfer.files[0]);
});
dropZone.addEventListener("click",function(e){
  if(e.target.tagName==="BUTTON")return;
  fileInput.click();
});
dropZone.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();fileInput.click()}});
fileInput.addEventListener("change",function(){if(fileInput.files.length)loadFile(fileInput.files[0])});

document.getElementById("btnSave").addEventListener("click",saveFile);
document.getElementById("btnSnbt").addEventListener("click",exportSNBT);
document.getElementById("btnCloseFile").addEventListener("click",closeEditor);
document.getElementById("btnAddRoot").addEventListener("click",function(){
  if(currentRoot)openAddTagModal(currentRoot,rootWrapper);
});
document.getElementById("btnSearch").addEventListener("click",runSearch);
document.getElementById("btnCollapse").addEventListener("click",function(){
  renderTree();
  searchResults.classList.remove("visible");
});
searchInput.addEventListener("keydown",function(e){if(e.key==="Enter"){e.preventDefault();runSearch()}});
searchInput.addEventListener("search",function(){if(!searchInput.value)searchResults.classList.remove("visible")});

document.getElementById("newTagType").addEventListener("change",function(){
  document.getElementById("listSubtypeRow").style.display=(parseInt(this.value,10)===TAG.LIST)?"block":"none";
});
document.getElementById("addTagCancel").addEventListener("click",closeAddModal);
document.getElementById("addTagConfirm").addEventListener("click",function(){
  if(!addTargetTag)return;
  const nameInput=document.getElementById("newTagName");
  const typeVal=parseInt(document.getElementById("newTagType").value,10);
  const valueStr=document.getElementById("newTagValue").value;
  const listSubtype=parseInt(document.getElementById("newListSubtype").value,10);
  try{
    const newTag=createDefaultTag(typeVal,valueStr,listSubtype);
    if(addTargetTag.type===TAG.COMPOUND){
      const name=nameInput.value.trim();
      if(!name)throw new Error(t("nameneeded","Tag name is required"));
      if(addTargetTag.value.some(function(t){return t.name===name}))throw new Error(t("nametaken","A tag named {0} already exists here",name));
      newTag.name=name;
      addTargetTag.value.push(newTag);
    }else if(addTargetTag.type===TAG.LIST){
      if(addTargetTag.value.length&&addTargetTag.value[0].type!==newTag.type)
        throw new Error(t("listtype","List already holds {0} entries",TAG_NAMES[addTargetTag.value[0].type]));
      addTargetTag.listType=newTag.type;
      addTargetTag.value.push(newTag);
    }
    const w=addTargetWrapper;
    closeAddModal();
    if(w&&w._rebuild){const fresh=w._rebuild();fresh._expand()}
    else renderTree();
    toast(t("tagadded","Tag added"),"success");
  }catch(err){
    toast(t("error","Error: {0}",err.message),"error");
  }
});
function closeAddModal(){
  addTagModal.classList.remove("visible");
  addTargetTag=null;
  addTargetWrapper=null;
  document.getElementById("newTagType").disabled=false;
}
addTagModal.addEventListener("click",function(e){if(e.target===addTagModal)closeAddModal()});

document.getElementById("arrayModalCancel").addEventListener("click",closeArrayModal);
document.getElementById("arrayModalConfirm").addEventListener("click",function(){
  if(!arrayTargetTag)return;
  try{
    const text=document.getElementById("arrayModalText").value;
    arrayTargetTag.value=parseArrayText(arrayTargetTag.type,text);
    if(arrayTargetEl)arrayTargetEl.textContent=formatValue(arrayTargetTag);
    const tag=arrayTargetTag;
    closeArrayModal();
    /* rebuild the array node so its children match the new contents */
    if(rootWrapper){
      const path=findTagPath(function(t){return t===tag});
      if(path&&path.length){
        let w=rootWrapper;
        for(let i=0;i<path.length;i++){w._expand();w=w._ensureChild(path[i]);if(!w)break}
        if(w&&w._rebuild)w._rebuild();
      }
    }
    toast(t("arrayupdated","Array updated"),"success");
  }catch(err){
    toast(t("badarray","Invalid array: {0}",err.message),"error");
  }
});
function closeArrayModal(){
  arrayModal.classList.remove("visible");
  arrayTargetTag=null;
  arrayTargetEl=null;
}
arrayModal.addEventListener("click",function(e){if(e.target===arrayModal)closeArrayModal()});

document.addEventListener("keydown",function(e){
  if(e.key!=="Escape")return;
  if(addTagModal.classList.contains("visible"))closeAddModal();
  if(arrayModal.classList.contains("visible"))closeArrayModal();
});

/* paste a file straight into the page */
document.addEventListener("paste",function(e){
  if(!e.clipboardData||!e.clipboardData.files||!e.clipboardData.files.length)return;
  loadFile(e.clipboardData.files[0]);
});

if(!streamsSupported()){
  console.warn("Compression Streams API missing: gzip/zlib files cannot be opened in this browser.");
}

/* ===== PUBLIC API =====
   Exposed so other tools can reuse the parser/writer from this page:
     NBT.read(uint8) -> {root, format, compression, headerVersion}
     NBT.write(root, formatId, {compression, headerVersion}) -> Promise<Uint8Array>
     NBT.toSNBT(tag, indent)
*/
window.NBT={
  TAG:TAG,
  TAG_NAMES:TAG_NAMES,
  FORMATS:FORMATS,
  sniffCompression:sniffCompression,
  decompress:decompressBytes,
  compress:compressBytes,
  parseWithFormat:parseWithFormat,
  detectFormat:detectFormat,
  serialize:serialize,
  toSNBT:toSNBT,
  read:async function(bytes){
    const compression=sniffCompression(bytes);
    const plain=await decompressBytes(bytes,compression);
    const det=detectFormat(plain);
    return{root:det.result.root,format:det.formatId,compression:compression,
      headerVersion:det.result.headerVersion,exact:!!det.exact,
      consumed:det.result.consumed,total:det.result.total};
  },
  write:async function(root,formatId,opts){
    const o=opts||{};
    const raw=serialize(root,formatId||"java",o.headerVersion==null?8:o.headerVersion);
    return compressBytes(raw,o.compression||"none");
  }
};

})();
