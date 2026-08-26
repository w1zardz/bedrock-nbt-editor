/* Language switching: remembers the choice in a cookie, offers the browser's
   language on a first visit, and never fights an explicit click. */
(function(){
"use strict";
var COOKIE="nbtlang";
var MAXAGE=60*60*24*365;
var urls=window.__LANG_URLS__||{};
var current=document.documentElement.lang||"en";

function readCookie(){
  var m=document.cookie.match(/(?:^|;\s*)nbtlang=([^;]+)/);
  return m?decodeURIComponent(m[1]):"";
}
function writeCookie(code){
  try{
    document.cookie=COOKIE+"="+encodeURIComponent(code)+";path=/;max-age="+MAXAGE+";SameSite=Lax";
  }catch(e){/* cookies blocked — the click still navigates */}
}
function flag(key,value){
  try{if(value===undefined)return sessionStorage.getItem(key);sessionStorage.setItem(key,value)}
  catch(e){return null}
}

/* explicit choice wins and is remembered */
document.addEventListener("click",function(e){
  var el=e.target.closest?e.target.closest("[data-lang]"):null;
  if(!el)return;
  writeCookie(el.getAttribute("data-lang"));
  flag("nbtlang-redirected","1");
});

/* close the dropdown when clicking outside it */
document.addEventListener("click",function(e){
  var open=document.querySelector(".lang-switch[open]");
  if(open&&!open.contains(e.target))open.removeAttribute("open");
});

var saved=readCookie();

/* saved language differs from the page being viewed: follow the saved one, once */
if(saved&&saved!==current&&urls[saved]&&!flag("nbtlang-redirected")){
  flag("nbtlang-redirected","1");
  location.replace(urls[saved]);
  return;
}

/* no choice yet: offer the browser's language instead of hijacking the page */
if(!saved){
  var wanted="";
  var prefs=navigator.languages||[navigator.language||""];
  for(var i=0;i<prefs.length&&!wanted;i++){
    var base=String(prefs[i]).toLowerCase().split("-")[0];
    for(var code in urls){
      if(code===current)continue;
      if(code===base||code.split("-")[0]===base){wanted=code;break}
    }
  }
  if(wanted)offer(wanted);
}

function offer(code){
  var strings=window.__NBT_STRINGS__||{};
  var link=document.querySelector('.lang-menu a[data-lang="'+code+'"]');
  if(!link)return;
  var name=link.textContent.replace(/\s*\(beta\)\s*$/,"");
  var bar=document.createElement("div");
  bar.className="lang-offer";
  bar.setAttribute("role","region");
  var text=document.createElement("span");
  text.textContent=(strings.langprompt||"Open this page in {0}?").replace("{0}",name);
  var yes=document.createElement("a");
  yes.href=urls[code];
  yes.setAttribute("data-lang",code);
  yes.className="lang-offer-yes";
  yes.textContent=strings.langyes||"Switch";
  var no=document.createElement("button");
  no.type="button";
  no.className="lang-offer-no";
  no.textContent=strings.langno||"Stay";
  no.addEventListener("click",function(){writeCookie(current);bar.remove()});
  bar.appendChild(text);bar.appendChild(yes);bar.appendChild(no);
  document.body.appendChild(bar);
}
})();
