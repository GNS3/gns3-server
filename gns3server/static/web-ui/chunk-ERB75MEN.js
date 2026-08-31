import{$ as D,$a as fe,Bd as Mt,Cb as kt,D as ie,Db as wt,Dc as Ce,Dd as Oe,E as rt,Ea as k,Eb as O,Fa as ue,Fb as Tt,G as f,Ga as me,Gd as Ft,Ge as Pe,He as ut,Ia as ge,Id as Me,Jc as At,L as N,Ma as A,Na as E,Nc as Se,Oa as L,Oc as Ie,P as ae,Qa as he,Qb as be,Qc as Et,Ra as Z,S as re,Sa as Y,Uc as $t,Ue as Le,V as pt,We as Be,Xa as m,Xc as ke,Y as ft,Yc as lt,Ye as je,Za as pe,_ as se,_b as ve,a as M,aa as x,b as Xt,ba as h,bf as Nt,ca as S,cc as Dt,cd as j,cf as ze,da as l,eb as B,ef as Ge,fb as v,fd as we,g as te,gb as w,h as Ht,hb as X,i as T,ia as Ut,j as ee,ja as le,k as Vt,ka as F,kc as st,ke as Rt,la as J,ld as z,mc as y,na as P,nb as yt,nc as xt,nd as Qt,ne as ot,oa as ce,od as Te,p as Q,pa as _t,pb as Wt,pd as De,q as g,qa as bt,qb as tt,sa as de,sb as Ct,sd as ct,se as Fe,t as ne,ta as vt,tb as St,td as dt,te as Re,u as q,ua as I,ub as It,uc as ye,ud as nt,vb as _e,vd as Ot,ve as Ne,wb as et,xb as U,xd as xe,y as ht,ya as K,yb as W,yd as Ae,z as oe,zd as Ee}from"./chunk-TYGV4UPE.js";var dn=["determinateSpinner"];function un(o,s){if(o&1&&(Ut(),v(0,"svg",11),X(1,"circle",12),w()),o&2){let t=Ct();m("viewBox",t._viewBox()),k(),wt("stroke-dasharray",t._strokeCircumference(),"px")("stroke-dashoffset",t._strokeCircumference()/2,"px")("stroke-width",t._circleStrokeWidth(),"%"),m("r",t._circleRadius())}}var mn=new h("mat-progress-spinner-default-options",{providedIn:"root",factory:()=>({diameter:He})}),He=100,gn=10,io=(()=>{class o{_elementRef=l(I);_noopAnimations;get color(){return this._color||this._defaultColor}set color(t){this._color=t}_color;_defaultColor="primary";_determinateCircle;constructor(){let t=l(mn),e=Pe(),n=this._elementRef.nativeElement;this._noopAnimations=e==="di-disabled"&&!!t&&!t._forceAnimations,this.mode=n.nodeName.toLowerCase()==="mat-spinner"?"indeterminate":"determinate",!this._noopAnimations&&e==="reduced-motion"&&n.classList.add("mat-progress-spinner-reduced-motion"),t&&(t.color&&(this.color=this._defaultColor=t.color),t.diameter&&(this.diameter=t.diameter),t.strokeWidth&&(this.strokeWidth=t.strokeWidth))}mode;get value(){return this.mode==="determinate"?this._value:0}set value(t){this._value=Math.max(0,Math.min(100,t||0))}_value=0;get diameter(){return this._diameter}set diameter(t){this._diameter=t||0}_diameter=He;get strokeWidth(){return this._strokeWidth??this.diameter/10}set strokeWidth(t){this._strokeWidth=t||0}_strokeWidth;_circleRadius(){return(this.diameter-gn)/2}_viewBox(){let t=this._circleRadius()*2+this.strokeWidth;return`0 0 ${t} ${t}`}_strokeCircumference(){return 2*Math.PI*this._circleRadius()}_strokeDashOffset(){return this.mode==="determinate"?this._strokeCircumference()*(100-this._value)/100:null}_circleStrokeWidth(){return this.strokeWidth/this.diameter*100}static \u0275fac=function(e){return new(e||o)};static \u0275cmp=A({type:o,selectors:[["mat-progress-spinner"],["mat-spinner"]],viewQuery:function(e,n){if(e&1&&et(dn,5),e&2){let i;U(i=W())&&(n._determinateCircle=i.first)}},hostAttrs:["role","progressbar","tabindex","-1",1,"mat-mdc-progress-spinner","mdc-circular-progress"],hostVars:18,hostBindings:function(e,n){e&2&&(m("aria-valuemin",0)("aria-valuemax",100)("aria-valuenow",n.mode==="determinate"?n.value:null)("mode",n.mode),Tt("mat-"+n.color),wt("width",n.diameter,"px")("height",n.diameter,"px")("--mat-progress-spinner-size",n.diameter+"px")("--mat-progress-spinner-active-indicator-width",n.diameter+"px"),O("_mat-animation-noopable",n._noopAnimations)("mdc-circular-progress--indeterminate",n.mode==="indeterminate"))},inputs:{color:"color",mode:"mode",value:[2,"value","value",xt],diameter:[2,"diameter","diameter",xt],strokeWidth:[2,"strokeWidth","strokeWidth",xt]},exportAs:["matProgressSpinner"],decls:14,vars:11,consts:[["circle",""],["determinateSpinner",""],["aria-hidden","true",1,"mdc-circular-progress__determinate-container"],["xmlns","http://www.w3.org/2000/svg","focusable","false",1,"mdc-circular-progress__determinate-circle-graphic"],["cx","50%","cy","50%",1,"mdc-circular-progress__determinate-circle"],["aria-hidden","true",1,"mdc-circular-progress__indeterminate-container"],[1,"mdc-circular-progress__spinner-layer"],[1,"mdc-circular-progress__circle-clipper","mdc-circular-progress__circle-left"],[3,"ngTemplateOutlet"],[1,"mdc-circular-progress__gap-patch"],[1,"mdc-circular-progress__circle-clipper","mdc-circular-progress__circle-right"],["xmlns","http://www.w3.org/2000/svg","focusable","false",1,"mdc-circular-progress__indeterminate-circle-graphic"],["cx","50%","cy","50%"]],template:function(e,n){if(e&1&&(Y(0,un,2,8,"ng-template",null,0,ve),v(2,"div",2,1),Ut(),v(4,"svg",3),X(5,"circle",4),w()(),le(),v(6,"div",5)(7,"div",6)(8,"div",7),yt(9,8),w(),v(10,"div",9),yt(11,8),w(),v(12,"div",10),yt(13,8),w()()()),e&2){let i=kt(1);k(4),m("viewBox",n._viewBox()),k(),wt("stroke-dasharray",n._strokeCircumference(),"px")("stroke-dashoffset",n._strokeDashOffset(),"px")("stroke-width",n._circleStrokeWidth(),"%"),m("r",n._circleRadius()),k(4),B("ngTemplateOutlet",i),k(2),B("ngTemplateOutlet",i),k(2),B("ngTemplateOutlet",i)}},dependencies:[ye],styles:[`.mat-mdc-progress-spinner {
  --mat-progress-spinner-animation-multiplier: 1;
  display: block;
  overflow: hidden;
  line-height: 0;
  position: relative;
  direction: ltr;
  transition: opacity 250ms cubic-bezier(0.4, 0, 0.6, 1);
}
.mat-mdc-progress-spinner circle {
  stroke-width: var(--mat-progress-spinner-active-indicator-width, 4px);
}
.mat-mdc-progress-spinner._mat-animation-noopable, .mat-mdc-progress-spinner._mat-animation-noopable .mdc-circular-progress__determinate-circle {
  transition: none !important;
}
.mat-mdc-progress-spinner._mat-animation-noopable .mdc-circular-progress__indeterminate-circle-graphic,
.mat-mdc-progress-spinner._mat-animation-noopable .mdc-circular-progress__spinner-layer,
.mat-mdc-progress-spinner._mat-animation-noopable .mdc-circular-progress__indeterminate-container {
  animation: none !important;
}
.mat-mdc-progress-spinner._mat-animation-noopable .mdc-circular-progress__indeterminate-container circle {
  stroke-dasharray: 0 !important;
}
@media (forced-colors: active) {
  .mat-mdc-progress-spinner .mdc-circular-progress__indeterminate-circle-graphic,
  .mat-mdc-progress-spinner .mdc-circular-progress__determinate-circle {
    stroke: currentColor;
    stroke: CanvasText;
  }
}

.mat-progress-spinner-reduced-motion {
  --mat-progress-spinner-animation-multiplier: 1.25;
}

.mdc-circular-progress__determinate-container,
.mdc-circular-progress__indeterminate-circle-graphic,
.mdc-circular-progress__indeterminate-container,
.mdc-circular-progress__spinner-layer {
  position: absolute;
  width: 100%;
  height: 100%;
}

.mdc-circular-progress__determinate-container {
  transform: rotate(-90deg);
}
.mdc-circular-progress--indeterminate .mdc-circular-progress__determinate-container {
  opacity: 0;
}

.mdc-circular-progress__indeterminate-container {
  font-size: 0;
  letter-spacing: 0;
  white-space: nowrap;
  opacity: 0;
}
.mdc-circular-progress--indeterminate .mdc-circular-progress__indeterminate-container {
  opacity: 1;
  animation: mdc-circular-progress-container-rotate calc(1568.2352941176ms * var(--mat-progress-spinner-animation-multiplier)) linear infinite;
}

.mdc-circular-progress__determinate-circle-graphic,
.mdc-circular-progress__indeterminate-circle-graphic {
  fill: transparent;
}

.mat-mdc-progress-spinner .mdc-circular-progress__determinate-circle,
.mat-mdc-progress-spinner .mdc-circular-progress__indeterminate-circle-graphic {
  stroke: var(--mat-progress-spinner-active-indicator-color, var(--mat-sys-primary));
}
@media (forced-colors: active) {
  .mat-mdc-progress-spinner .mdc-circular-progress__determinate-circle,
  .mat-mdc-progress-spinner .mdc-circular-progress__indeterminate-circle-graphic {
    stroke: CanvasText;
  }
}

.mdc-circular-progress__determinate-circle {
  transition: stroke-dashoffset 500ms cubic-bezier(0, 0, 0.2, 1);
}

.mdc-circular-progress__gap-patch {
  position: absolute;
  top: 0;
  left: 47.5%;
  box-sizing: border-box;
  width: 5%;
  height: 100%;
  overflow: hidden;
}

.mdc-circular-progress__gap-patch .mdc-circular-progress__indeterminate-circle-graphic {
  left: -900%;
  width: 2000%;
  transform: rotate(180deg);
}
.mdc-circular-progress__circle-clipper .mdc-circular-progress__indeterminate-circle-graphic {
  width: 200%;
}
.mdc-circular-progress__circle-right .mdc-circular-progress__indeterminate-circle-graphic {
  left: -100%;
}
.mdc-circular-progress--indeterminate .mdc-circular-progress__circle-left .mdc-circular-progress__indeterminate-circle-graphic {
  animation: mdc-circular-progress-left-spin calc(1333ms * var(--mat-progress-spinner-animation-multiplier)) cubic-bezier(0.4, 0, 0.2, 1) infinite both;
}
.mdc-circular-progress--indeterminate .mdc-circular-progress__circle-right .mdc-circular-progress__indeterminate-circle-graphic {
  animation: mdc-circular-progress-right-spin calc(1333ms * var(--mat-progress-spinner-animation-multiplier)) cubic-bezier(0.4, 0, 0.2, 1) infinite both;
}

.mdc-circular-progress__circle-clipper {
  display: inline-flex;
  position: relative;
  width: 50%;
  height: 100%;
  overflow: hidden;
}

.mdc-circular-progress--indeterminate .mdc-circular-progress__spinner-layer {
  animation: mdc-circular-progress-spinner-layer-rotate calc(5332ms * var(--mat-progress-spinner-animation-multiplier)) cubic-bezier(0.4, 0, 0.2, 1) infinite both;
}

@keyframes mdc-circular-progress-container-rotate {
  to {
    transform: rotate(360deg);
  }
}
@keyframes mdc-circular-progress-spinner-layer-rotate {
  12.5% {
    transform: rotate(135deg);
  }
  25% {
    transform: rotate(270deg);
  }
  37.5% {
    transform: rotate(405deg);
  }
  50% {
    transform: rotate(540deg);
  }
  62.5% {
    transform: rotate(675deg);
  }
  75% {
    transform: rotate(810deg);
  }
  87.5% {
    transform: rotate(945deg);
  }
  100% {
    transform: rotate(1080deg);
  }
}
@keyframes mdc-circular-progress-left-spin {
  from {
    transform: rotate(265deg);
  }
  50% {
    transform: rotate(130deg);
  }
  to {
    transform: rotate(265deg);
  }
}
@keyframes mdc-circular-progress-right-spin {
  from {
    transform: rotate(-265deg);
  }
  50% {
    transform: rotate(-130deg);
  }
  to {
    transform: rotate(-265deg);
  }
}
`],encapsulation:2,changeDetection:0})}return o})();var ao=(()=>{class o{static \u0275fac=function(e){return new(e||o)};static \u0275mod=E({type:o});static \u0275inj=x({imports:[j]})}return o})();function Ve(o){return Error(`Unable to find icon with the name "${o}"`)}function pn(){return Error("Could not find HttpClient for use with Angular Material icons. Please add provideHttpClient() to your providers.")}function Ue(o){return Error(`The URL provided to MatIconRegistry was not trusted as a resource URL via Angular's DomSanitizer. Attempted URL was "${o}".`)}function We(o){return Error(`The literal provided to MatIconRegistry was not trusted as safe HTML by Angular's DomSanitizer. Attempted literal was "${o}".`)}var R=class{url;svgText;options;svgElement=null;constructor(s,t,e){this.url=s,this.svgText=t,this.options=e}},Qe=(()=>{class o{_httpClient;_sanitizer;_errorHandler;_document;_svgIconConfigs=new Map;_iconSetConfigs=new Map;_cachedIconsByUrl=new Map;_inProgressUrlFetches=new Map;_fontCssClassesByAlias=new Map;_resolvers=[];_defaultFontSetClass=["material-icons","mat-ligature-font"];constructor(t,e,n,i){this._httpClient=t,this._sanitizer=e,this._errorHandler=i,this._document=n}addSvgIcon(t,e,n){return this.addSvgIconInNamespace("",t,e,n)}addSvgIconLiteral(t,e,n){return this.addSvgIconLiteralInNamespace("",t,e,n)}addSvgIconInNamespace(t,e,n,i){return this._addSvgIconConfig(t,e,new R(n,null,i))}addSvgIconResolver(t){return this._resolvers.push(t),this}addSvgIconLiteralInNamespace(t,e,n,i){let a=this._sanitizer.sanitize(K.HTML,n);if(!a)throw We(n);let r=ot(a);return this._addSvgIconConfig(t,e,new R("",r,i))}addSvgIconSet(t,e){return this.addSvgIconSetInNamespace("",t,e)}addSvgIconSetLiteral(t,e){return this.addSvgIconSetLiteralInNamespace("",t,e)}addSvgIconSetInNamespace(t,e,n){return this._addSvgIconSetConfig(t,new R(e,null,n))}addSvgIconSetLiteralInNamespace(t,e,n){let i=this._sanitizer.sanitize(K.HTML,e);if(!i)throw We(e);let a=ot(i);return this._addSvgIconSetConfig(t,new R("",a,n))}registerFontClassAlias(t,e=t){return this._fontCssClassesByAlias.set(t,e),this}classNameForFontAlias(t){return this._fontCssClassesByAlias.get(t)||t}setDefaultFontSetClass(...t){return this._defaultFontSetClass=t,this}getDefaultFontSetClass(){return this._defaultFontSetClass}getSvgIconFromUrl(t){let e=this._sanitizer.sanitize(K.RESOURCE_URL,t);if(!e)throw Ue(t);let n=this._cachedIconsByUrl.get(e);return n?Q(Pt(n)):this._loadSvgIconFromConfig(new R(t,null)).pipe(ft(i=>this._cachedIconsByUrl.set(e,i)),q(i=>Pt(i)))}getNamedSvgIcon(t,e=""){let n=$e(e,t),i=this._svgIconConfigs.get(n);if(i)return this._getSvgFromConfig(i);if(i=this._getIconConfigFromResolvers(e,t),i)return this._svgIconConfigs.set(n,i),this._getSvgFromConfig(i);let a=this._iconSetConfigs.get(e);return a?this._getSvgFromIconSetConfigs(t,a):g(Ve(n))}ngOnDestroy(){this._resolvers=[],this._svgIconConfigs.clear(),this._iconSetConfigs.clear(),this._cachedIconsByUrl.clear()}_getSvgFromConfig(t){return t.svgText?Q(Pt(this._svgElementFromConfig(t))):this._loadSvgIconFromConfig(t).pipe(q(e=>Pt(e)))}_getSvgFromIconSetConfigs(t,e){let n=this._extractIconWithNameFromAnySet(t,e);if(n)return Q(n);let i=e.filter(a=>!a.svgText).map(a=>this._loadSvgIconSetFromConfig(a).pipe(f(r=>{let c=`Loading icon set URL: ${this._sanitizer.sanitize(K.RESOURCE_URL,a.url)} failed: ${r.message}`;return this._errorHandler.handleError(new Error(c)),Q(null)})));return oe(i).pipe(q(()=>{let a=this._extractIconWithNameFromAnySet(t,e);if(!a)throw Ve(t);return a}))}_extractIconWithNameFromAnySet(t,e){for(let n=e.length-1;n>=0;n--){let i=e[n];if(i.svgText&&i.svgText.toString().indexOf(t)>-1){let a=this._svgElementFromConfig(i),r=this._extractSvgIconFromSet(a,t,i.options);if(r)return r}}return null}_loadSvgIconFromConfig(t){return this._fetchIcon(t).pipe(ft(e=>t.svgText=e),q(()=>this._svgElementFromConfig(t)))}_loadSvgIconSetFromConfig(t){return t.svgText?Q(null):this._fetchIcon(t).pipe(ft(e=>t.svgText=e))}_extractSvgIconFromSet(t,e,n){let i=t.querySelector(`[id="${e}"]`);if(!i)return null;let a=i.cloneNode(!0);if(a.removeAttribute("id"),a.nodeName.toLowerCase()==="svg")return this._setSvgAttributes(a,n);if(a.nodeName.toLowerCase()==="symbol")return this._setSvgAttributes(this._toSvgElement(a),n);let r=this._svgElementFromString(ot("<svg></svg>"));return r.appendChild(a),this._setSvgAttributes(r,n)}_svgElementFromString(t){let e=this._document.createElement("DIV");e.innerHTML=t;let n=e.querySelector("svg");if(!n)throw Error("<svg> tag not found");return n}_toSvgElement(t){let e=this._svgElementFromString(ot("<svg></svg>")),n=t.attributes;for(let i=0;i<n.length;i++){let{name:a,value:r}=n[i];a!=="id"&&e.setAttribute(a,r)}for(let i=0;i<t.childNodes.length;i++)t.childNodes[i].nodeType===this._document.ELEMENT_NODE&&e.appendChild(t.childNodes[i].cloneNode(!0));return e}_setSvgAttributes(t,e){return t.setAttribute("fit",""),t.setAttribute("height","100%"),t.setAttribute("width","100%"),t.setAttribute("preserveAspectRatio","xMidYMid meet"),t.setAttribute("focusable","false"),e&&e.viewBox&&t.setAttribute("viewBox",e.viewBox),t}_fetchIcon(t){let{url:e,options:n}=t,i=n?.withCredentials??!1;if(!this._httpClient)throw pn();if(e==null)throw Error(`Cannot fetch icon from URL "${e}".`);let a=this._sanitizer.sanitize(K.RESOURCE_URL,e);if(!a)throw Ue(e);let r=this._inProgressUrlFetches.get(a);if(r)return r;let d=this._httpClient.get(a,{responseType:"text",withCredentials:i}).pipe(q(c=>ot(c)),ae(()=>this._inProgressUrlFetches.delete(a)),re());return this._inProgressUrlFetches.set(a,d),d}_addSvgIconConfig(t,e,n){return this._svgIconConfigs.set($e(t,e),n),this}_addSvgIconSetConfig(t,e){let n=this._iconSetConfigs.get(t);return n?n.push(e):this._iconSetConfigs.set(t,[e]),this}_svgElementFromConfig(t){if(!t.svgElement){let e=this._svgElementFromString(t.svgText);this._setSvgAttributes(e,t.options),t.svgElement=e}return t.svgElement}_getIconConfigFromResolvers(t,e){for(let n=0;n<this._resolvers.length;n++){let i=this._resolvers[n](e,t);if(i)return fn(i)?new R(i.url,null,i.options):new R(i,null)}}static \u0275fac=function(e){return new(e||o)(S(At,8),S(Se),S(J,8),S(_t))};static \u0275prov=D({token:o,factory:o.\u0275fac,providedIn:"root"})}return o})();function Pt(o){return o.cloneNode(!0)}function $e(o,s){return o+":"+s}function fn(o){return!!(o.url&&o.options)}var _n=["*"],bn=new h("MAT_ICON_DEFAULT_OPTIONS"),vn=new h("mat-icon-location",{providedIn:"root",factory:()=>{let o=l(J),s=o?o.location:null;return{getPathname:()=>s?s.pathname+s.search:""}}}),qe=["clip-path","color-profile","src","cursor","fill","filter","marker","marker-start","marker-mid","marker-end","mask","stroke"],yn=qe.map(o=>`[${o}]`).join(", "),Cn=/^url\(['"]?#(.*?)['"]?\)$/,Do=(()=>{class o{_elementRef=l(I);_iconRegistry=l(Qe);_location=l(vn);_errorHandler=l(_t);_defaultColor;get color(){return this._color||this._defaultColor}set color(t){this._color=t}_color;inline=!1;get svgIcon(){return this._svgIcon}set svgIcon(t){t!==this._svgIcon&&(t?this._updateSvgIcon(t):this._svgIcon&&this._clearSvgElement(),this._svgIcon=t)}_svgIcon;get fontSet(){return this._fontSet}set fontSet(t){let e=this._cleanupFontValue(t);e!==this._fontSet&&(this._fontSet=e,this._updateFontIconClasses())}_fontSet;get fontIcon(){return this._fontIcon}set fontIcon(t){let e=this._cleanupFontValue(t);e!==this._fontIcon&&(this._fontIcon=e,this._updateFontIconClasses())}_fontIcon;_previousFontSetClass=[];_previousFontIconClass;_svgName=null;_svgNamespace=null;_previousPath;_elementsWithExternalReferences;_currentIconFetch=te.EMPTY;constructor(){let t=l(new Dt("aria-hidden"),{optional:!0}),e=l(bn,{optional:!0});e&&(e.color&&(this.color=this._defaultColor=e.color),e.fontSet&&(this.fontSet=e.fontSet)),t||this._elementRef.nativeElement.setAttribute("aria-hidden","true")}_splitIconName(t){if(!t)return["",""];let e=t.split(":");switch(e.length){case 1:return["",e[0]];case 2:return e;default:throw Error(`Invalid icon name: "${t}"`)}}ngOnInit(){this._updateFontIconClasses()}ngAfterViewChecked(){let t=this._elementsWithExternalReferences;if(t&&t.size){let e=this._location.getPathname();e!==this._previousPath&&(this._previousPath=e,this._prependPathToReferences(e))}}ngOnDestroy(){this._currentIconFetch.unsubscribe(),this._elementsWithExternalReferences&&this._elementsWithExternalReferences.clear()}_usingFontIcon(){return!this.svgIcon}_setSvgElement(t){this._clearSvgElement();let e=this._location.getPathname();this._previousPath=e,this._cacheChildrenWithExternalReferences(t),this._prependPathToReferences(e),this._elementRef.nativeElement.appendChild(t)}_clearSvgElement(){let t=this._elementRef.nativeElement,e=t.childNodes.length;for(this._elementsWithExternalReferences&&this._elementsWithExternalReferences.clear();e--;){let n=t.childNodes[e];(n.nodeType!==1||n.nodeName.toLowerCase()==="svg")&&n.remove()}}_updateFontIconClasses(){if(!this._usingFontIcon())return;let t=this._elementRef.nativeElement,e=(this.fontSet?this._iconRegistry.classNameForFontAlias(this.fontSet).split(/ +/):this._iconRegistry.getDefaultFontSetClass()).filter(n=>n.length>0);this._previousFontSetClass.forEach(n=>t.classList.remove(n)),e.forEach(n=>t.classList.add(n)),this._previousFontSetClass=e,this.fontIcon!==this._previousFontIconClass&&!e.includes("mat-ligature-font")&&(this._previousFontIconClass&&t.classList.remove(this._previousFontIconClass),this.fontIcon&&t.classList.add(this.fontIcon),this._previousFontIconClass=this.fontIcon)}_cleanupFontValue(t){return typeof t=="string"?t.trim().split(" ")[0]:t}_prependPathToReferences(t){let e=this._elementsWithExternalReferences;e&&e.forEach((n,i)=>{n.forEach(a=>{i.setAttribute(a.name,`url('${t}#${a.value}')`)})})}_cacheChildrenWithExternalReferences(t){let e=t.querySelectorAll(yn),n=this._elementsWithExternalReferences=this._elementsWithExternalReferences||new Map;for(let i=0;i<e.length;i++)qe.forEach(a=>{let r=e[i],d=r.getAttribute(a),c=d?d.match(Cn):null;if(c){let C=n.get(r);C||(C=[],n.set(r,C)),C.push({name:a,value:c[1]})}})}_updateSvgIcon(t){if(this._svgNamespace=null,this._svgName=null,this._currentIconFetch.unsubscribe(),t){let[e,n]=this._splitIconName(t);e&&(this._svgNamespace=e),n&&(this._svgName=n),this._currentIconFetch=this._iconRegistry.getNamedSvgIcon(n,e).pipe(N(1)).subscribe(i=>this._setSvgElement(i),i=>{let a=`Error retrieving icon ${e}:${n}! ${i.message}`;this._errorHandler.handleError(new Error(a))})}}static \u0275fac=function(e){return new(e||o)};static \u0275cmp=A({type:o,selectors:[["mat-icon"]],hostAttrs:["role","img",1,"mat-icon","notranslate"],hostVars:10,hostBindings:function(e,n){e&2&&(m("data-mat-icon-type",n._usingFontIcon()?"font":"svg")("data-mat-icon-name",n._svgName||n.fontIcon)("data-mat-icon-namespace",n._svgNamespace||n.fontSet)("fontIcon",n._usingFontIcon()?n.fontIcon:null),Tt(n.color?"mat-"+n.color:""),O("mat-icon-inline",n.inline)("mat-icon-no-color",n.color!=="primary"&&n.color!=="accent"&&n.color!=="warn"))},inputs:{color:"color",inline:[2,"inline","inline",y],svgIcon:"svgIcon",fontSet:"fontSet",fontIcon:"fontIcon"},exportAs:["matIcon"],ngContentSelectors:_n,decls:1,vars:0,template:function(e,n){e&1&&(St(),It(0))},styles:[`mat-icon, mat-icon.mat-primary, mat-icon.mat-accent, mat-icon.mat-warn {
  color: var(--mat-icon-color, inherit);
}

.mat-icon {
  -webkit-user-select: none;
  user-select: none;
  background-repeat: no-repeat;
  display: inline-block;
  fill: currentColor;
  height: 24px;
  width: 24px;
  overflow: hidden;
}
.mat-icon.mat-icon-inline {
  font-size: inherit;
  height: inherit;
  line-height: inherit;
  width: inherit;
}
.mat-icon.mat-ligature-font[fontIcon]::before {
  content: attr(fontIcon);
}

[dir=rtl] .mat-icon-rtl-mirror {
  transform: scale(-1, 1);
}

.mat-form-field:not(.mat-form-field-appearance-legacy) .mat-form-field-prefix .mat-icon,
.mat-form-field:not(.mat-form-field-appearance-legacy) .mat-form-field-suffix .mat-icon {
  display: block;
}
.mat-form-field:not(.mat-form-field-appearance-legacy) .mat-form-field-prefix .mat-icon-button .mat-icon,
.mat-form-field:not(.mat-form-field-appearance-legacy) .mat-form-field-suffix .mat-icon-button .mat-icon {
  margin: auto;
}
`],encapsulation:2,changeDetection:0})}return o})(),xo=(()=>{class o{static \u0275fac=function(e){return new(e||o)};static \u0275mod=E({type:o});static \u0275inj=x({imports:[j]})}return o})();function Sn(o,s){}var G=class{viewContainerRef;injector;id;role="dialog";panelClass="";hasBackdrop=!0;backdropClass="";disableClose=!1;closePredicate;width="";height="";minWidth;minHeight;maxWidth;maxHeight;positionStrategy;data=null;direction;ariaDescribedBy=null;ariaLabelledBy=null;ariaLabel=null;ariaModal=!1;autoFocus="first-tabbable";restoreFocus=!0;scrollStrategy;closeOnNavigation=!0;closeOnDestroy=!0;closeOnOverlayDetachments=!0;disableAnimations=!1;providers;container;templateContext};var Jt=(()=>{class o extends De{_elementRef=l(I);_focusTrapFactory=l(Re);_config;_interactivityChecker=l(Fe);_ngZone=l(ce);_focusMonitor=l(Rt);_renderer=l(ge);_changeDetectorRef=l(st);_injector=l(F);_platform=l(ke);_document=l(J);_portalOutlet;_focusTrapped=new T;_focusTrap=null;_elementFocusedBeforeDialogWasOpened=null;_closeInteractionType=null;_ariaLabelledByQueue=[];_isDestroyed=!1;constructor(){super(),this._config=l(G,{optional:!0})||new G,this._config.ariaLabelledBy&&this._ariaLabelledByQueue.push(this._config.ariaLabelledBy)}_addAriaLabelledBy(t){this._ariaLabelledByQueue.push(t),this._changeDetectorRef.markForCheck()}_removeAriaLabelledBy(t){let e=this._ariaLabelledByQueue.indexOf(t);e>-1&&(this._ariaLabelledByQueue.splice(e,1),this._changeDetectorRef.markForCheck())}_contentAttached(){this._initializeFocusTrap(),this._captureInitialFocus()}_captureInitialFocus(){this._trapFocus()}ngOnDestroy(){this._focusTrapped.complete(),this._isDestroyed=!0,this._restoreFocus()}attachComponentPortal(t){this._portalOutlet.hasAttached();let e=this._portalOutlet.attachComponentPortal(t);return this._contentAttached(),e}attachTemplatePortal(t){this._portalOutlet.hasAttached();let e=this._portalOutlet.attachTemplatePortal(t);return this._contentAttached(),e}attachDomPortal=t=>{this._portalOutlet.hasAttached();let e=this._portalOutlet.attachDomPortal(t);return this._contentAttached(),e};_recaptureFocus(){this._containsFocus()||this._trapFocus()}_forceFocus(t,e){this._interactivityChecker.isFocusable(t)||(t.tabIndex=-1,this._ngZone.runOutsideAngular(()=>{let n=()=>{i(),a(),t.removeAttribute("tabindex")},i=this._renderer.listen(t,"blur",n),a=this._renderer.listen(t,"mousedown",n)})),t.focus(e)}_focusByCssSelector(t,e){let n=this._elementRef.nativeElement.querySelector(t);n&&this._forceFocus(n,e)}_trapFocus(t){this._isDestroyed||ue(()=>{let e=this._elementRef.nativeElement;switch(this._config.autoFocus){case!1:case"dialog":this._containsFocus()||e.focus(t);break;case!0:case"first-tabbable":this._focusTrap?.focusInitialElement(t)||this._focusDialogContainer(t);break;case"first-heading":this._focusByCssSelector('h1, h2, h3, h4, h5, h6, [role="heading"]',t);break;default:this._focusByCssSelector(this._config.autoFocus,t);break}this._focusTrapped.next()},{injector:this._injector})}_restoreFocus(){let t=this._config.restoreFocus,e=null;if(typeof t=="string"?e=this._document.querySelector(t):typeof t=="boolean"?e=t?this._elementFocusedBeforeDialogWasOpened:null:t&&(e=t),this._config.restoreFocus&&e&&typeof e.focus=="function"){let n=Et(),i=this._elementRef.nativeElement;(!n||n===this._document.body||n===i||i.contains(n))&&(this._focusMonitor?(this._focusMonitor.focusVia(e,this._closeInteractionType),this._closeInteractionType=null):e.focus())}this._focusTrap&&this._focusTrap.destroy()}_focusDialogContainer(t){this._elementRef.nativeElement.focus?.(t)}_containsFocus(){let t=this._elementRef.nativeElement,e=Et();return t===e||t.contains(e)}_initializeFocusTrap(){this._platform.isBrowser&&(this._focusTrap=this._focusTrapFactory.create(this._elementRef.nativeElement),this._document&&(this._elementFocusedBeforeDialogWasOpened=Et()))}static \u0275fac=function(e){return new(e||o)};static \u0275cmp=A({type:o,selectors:[["cdk-dialog-container"]],viewQuery:function(e,n){if(e&1&&et(ct,7),e&2){let i;U(i=W())&&(n._portalOutlet=i.first)}},hostAttrs:["tabindex","-1",1,"cdk-dialog-container"],hostVars:6,hostBindings:function(e,n){e&2&&m("id",n._config.id||null)("role",n._config.role)("aria-modal",n._config.ariaModal)("aria-labelledby",n._config.ariaLabel?null:n._ariaLabelledByQueue[0])("aria-label",n._config.ariaLabel)("aria-describedby",n._config.ariaDescribedBy||null)},features:[Z],decls:1,vars:0,consts:[["cdkPortalOutlet",""]],template:function(e,n){e&1&&Y(0,Sn,0,0,"ng-template",0)},dependencies:[ct],styles:[`.cdk-dialog-container {
  display: block;
  width: 100%;
  height: 100%;
  min-height: inherit;
  max-height: inherit;
}
`],encapsulation:2})}return o})(),mt=class{overlayRef;config;componentInstance=null;componentRef=null;containerInstance;disableClose;closed=new T;backdropClick;keydownEvents;outsidePointerEvents;id;_detachSubscription;constructor(s,t){this.overlayRef=s,this.config=t,this.disableClose=t.disableClose,this.backdropClick=s.backdropClick(),this.keydownEvents=s.keydownEvents(),this.outsidePointerEvents=s.outsidePointerEvents(),this.id=t.id,this.keydownEvents.subscribe(e=>{e.keyCode===27&&!this.disableClose&&!nt(e)&&(e.preventDefault(),this.close(void 0,{focusOrigin:"keyboard"}))}),this.backdropClick.subscribe(()=>{!this.disableClose&&this._canClose()?this.close(void 0,{focusOrigin:"mouse"}):this.containerInstance._recaptureFocus?.()}),this._detachSubscription=s.detachments().subscribe(()=>{t.closeOnOverlayDetachments!==!1&&this.close()})}close(s,t){if(this._canClose(s)){let e=this.closed;this.containerInstance._closeInteractionType=t?.focusOrigin||"program",this._detachSubscription.unsubscribe(),this.overlayRef.dispose(),e.next(s),e.complete(),this.componentInstance=this.containerInstance=null}}updatePosition(){return this.overlayRef.updatePosition(),this}updateSize(s="",t=""){return this.overlayRef.updateSize({width:s,height:t}),this}addPanelClass(s){return this.overlayRef.addPanelClass(s),this}removePanelClass(s){return this.overlayRef.removePanelClass(s),this}_canClose(s){let t=this.config;return!!this.containerInstance&&(!t.closePredicate||t.closePredicate(s,t,this.componentInstance))}},In=new h("DialogScrollStrategy",{providedIn:"root",factory:()=>{let o=l(F);return()=>Ot(o)}}),kn=new h("DialogData"),wn=new h("DefaultDialogConfig");function Tn(o){let s=bt(o),t=new P;return{valueSignal:s,get value(){return s()},change:t,ngOnDestroy(){t.complete()}}}var Kt=(()=>{class o{_injector=l(F);_defaultOptions=l(wn,{optional:!0});_parentDialog=l(o,{optional:!0,skipSelf:!0});_overlayContainer=l(Ae);_idGenerator=l(z);_openDialogsAtThisLevel=[];_afterAllClosedAtThisLevel=new T;_afterOpenedAtThisLevel=new T;_ariaHiddenElements=new Map;_scrollStrategy=l(In);get openDialogs(){return this._parentDialog?this._parentDialog.openDialogs:this._openDialogsAtThisLevel}get afterOpened(){return this._parentDialog?this._parentDialog.afterOpened:this._afterOpenedAtThisLevel}afterAllClosed=ht(()=>this.openDialogs.length?this._getAfterAllClosed():this._getAfterAllClosed().pipe(pt(void 0)));constructor(){}open(t,e){let n=this._defaultOptions||new G;e=M(M({},n),e),e.id=e.id||this._idGenerator.getId("cdk-dialog-"),e.id&&this.getDialogById(e.id);let i=this._getOverlayConfig(e),a=Oe(this._injector,i),r=new mt(a,e),d=this._attachContainer(a,r,e);if(r.containerInstance=d,!this.openDialogs.length){let c=this._overlayContainer.getContainerElement();d._focusTrapped?d._focusTrapped.pipe(N(1)).subscribe(()=>{this._hideNonDialogContentFromAssistiveTechnology(c)}):this._hideNonDialogContentFromAssistiveTechnology(c)}return this._attachDialogContent(t,r,d,e),this.openDialogs.push(r),r.closed.subscribe(()=>this._removeOpenDialog(r,!0)),this.afterOpened.next(r),r}closeAll(){qt(this.openDialogs,t=>t.close())}getDialogById(t){return this.openDialogs.find(e=>e.id===t)}ngOnDestroy(){qt(this._openDialogsAtThisLevel,t=>{t.config.closeOnDestroy===!1&&this._removeOpenDialog(t,!1)}),qt(this._openDialogsAtThisLevel,t=>t.close()),this._afterAllClosedAtThisLevel.complete(),this._afterOpenedAtThisLevel.complete(),this._openDialogsAtThisLevel=[]}_getOverlayConfig(t){let e=new xe({positionStrategy:t.positionStrategy||Mt().centerHorizontally().centerVertically(),scrollStrategy:t.scrollStrategy||this._scrollStrategy(),panelClass:t.panelClass,hasBackdrop:t.hasBackdrop,direction:t.direction,minWidth:t.minWidth,minHeight:t.minHeight,maxWidth:t.maxWidth,maxHeight:t.maxHeight,width:t.width,height:t.height,disposeOnNavigation:t.closeOnNavigation,disableAnimations:t.disableAnimations});return t.backdropClass&&(e.backdropClass=t.backdropClass),e}_attachContainer(t,e,n){let i=n.injector||n.viewContainerRef?.injector,a=[{provide:G,useValue:n},{provide:mt,useValue:e},{provide:Ee,useValue:t}],r;n.container?typeof n.container=="function"?r=n.container:(r=n.container.type,a.push(...n.container.providers(n))):r=Jt;let d=new Qt(r,n.viewContainerRef,F.create({parent:i||this._injector,providers:a}));return t.attach(d).instance}_attachDialogContent(t,e,n,i){if(t instanceof me){let a=this._createInjector(i,e,n,void 0),r={$implicit:i.data,dialogRef:e};i.templateContext&&(r=M(M({},r),typeof i.templateContext=="function"?i.templateContext():i.templateContext)),n.attachTemplatePortal(new Te(t,null,r,a))}else{let a=this._createInjector(i,e,n,this._injector),r=n.attachComponentPortal(new Qt(t,i.viewContainerRef,a));e.componentRef=r,e.componentInstance=r.instance}}_createInjector(t,e,n,i){let a=t.injector||t.viewContainerRef?.injector,r=[{provide:kn,useValue:t.data},{provide:mt,useValue:e}];return t.providers&&(typeof t.providers=="function"?r.push(...t.providers(e,t,n)):r.push(...t.providers)),t.direction&&(!a||!a.get(lt,null,{optional:!0}))&&r.push({provide:lt,useValue:Tn(t.direction)}),F.create({parent:a||i,providers:r})}_removeOpenDialog(t,e){let n=this.openDialogs.indexOf(t);n>-1&&(this.openDialogs.splice(n,1),this.openDialogs.length||(this._ariaHiddenElements.forEach((i,a)=>{i?a.setAttribute("aria-hidden",i):a.removeAttribute("aria-hidden")}),this._ariaHiddenElements.clear(),e&&this._getAfterAllClosed().next()))}_hideNonDialogContentFromAssistiveTechnology(t){if(t.parentElement){let e=t.parentElement.children;for(let n=e.length-1;n>-1;n--){let i=e[n];i!==t&&i.nodeName!=="SCRIPT"&&i.nodeName!=="STYLE"&&!i.hasAttribute("aria-live")&&!i.hasAttribute("popover")&&(this._ariaHiddenElements.set(i,i.getAttribute("aria-hidden")),i.setAttribute("aria-hidden","true"))}}}_getAfterAllClosed(){let t=this._parentDialog;return t?t._getAfterAllClosed():this._afterAllClosedAtThisLevel}static \u0275fac=function(e){return new(e||o)};static \u0275prov=D({token:o,factory:o.\u0275fac,providedIn:"root"})}return o})();function qt(o,s){let t=o.length;for(;t--;)s(o[t])}var Ke=(()=>{class o{static \u0275fac=function(e){return new(e||o)};static \u0275mod=E({type:o});static \u0275inj=x({providers:[Kt],imports:[Ft,dt,Ne,dt]})}return o})();function Dn(o,s){}var Bt=class{viewContainerRef;injector;id;role="dialog";panelClass="";hasBackdrop=!0;backdropClass="";disableClose=!1;closePredicate;width="";height="";minWidth;minHeight;maxWidth;maxHeight;position;data=null;direction;ariaDescribedBy=null;ariaLabelledBy=null;ariaLabel=null;ariaModal=!1;autoFocus="first-tabbable";restoreFocus=!0;delayFocusTrap=!0;scrollStrategy;closeOnNavigation=!0;enterAnimationDuration;exitAnimationDuration},Zt="mdc-dialog--open",Ze="mdc-dialog--opening",Ye="mdc-dialog--closing",xn=150,An=75,En=(()=>{class o extends Jt{_animationStateChanged=new P;_animationsEnabled=!ut();_actionSectionCount=0;_hostElement=this._elementRef.nativeElement;_enterAnimationDuration=this._animationsEnabled?tn(this._config.enterAnimationDuration)??xn:0;_exitAnimationDuration=this._animationsEnabled?tn(this._config.exitAnimationDuration)??An:0;_animationTimer=null;_contentAttached(){super._contentAttached(),this._startOpenAnimation()}_startOpenAnimation(){this._animationStateChanged.emit({state:"opening",totalTime:this._enterAnimationDuration}),this._animationsEnabled?(this._hostElement.style.setProperty(Xe,`${this._enterAnimationDuration}ms`),this._requestAnimationFrame(()=>this._hostElement.classList.add(Ze,Zt)),this._waitForAnimationToComplete(this._enterAnimationDuration,this._finishDialogOpen)):(this._hostElement.classList.add(Zt),Promise.resolve().then(()=>this._finishDialogOpen()))}_startExitAnimation(){this._animationStateChanged.emit({state:"closing",totalTime:this._exitAnimationDuration}),this._hostElement.classList.remove(Zt),this._animationsEnabled?(this._hostElement.style.setProperty(Xe,`${this._exitAnimationDuration}ms`),this._requestAnimationFrame(()=>this._hostElement.classList.add(Ye)),this._waitForAnimationToComplete(this._exitAnimationDuration,this._finishDialogClose)):Promise.resolve().then(()=>this._finishDialogClose())}_updateActionSectionCount(t){this._actionSectionCount+=t,this._changeDetectorRef.markForCheck()}_finishDialogOpen=()=>{this._clearAnimationClasses(),this._openAnimationDone(this._enterAnimationDuration)};_finishDialogClose=()=>{this._clearAnimationClasses(),this._animationStateChanged.emit({state:"closed",totalTime:this._exitAnimationDuration})};_clearAnimationClasses(){this._hostElement.classList.remove(Ze,Ye)}_waitForAnimationToComplete(t,e){this._animationTimer!==null&&clearTimeout(this._animationTimer),this._animationTimer=setTimeout(e,t)}_requestAnimationFrame(t){this._ngZone.runOutsideAngular(()=>{typeof requestAnimationFrame=="function"?requestAnimationFrame(t):t()})}_captureInitialFocus(){this._config.delayFocusTrap||this._trapFocus()}_openAnimationDone(t){this._config.delayFocusTrap&&this._trapFocus(),this._animationStateChanged.next({state:"opened",totalTime:t})}ngOnDestroy(){super.ngOnDestroy(),this._animationTimer!==null&&clearTimeout(this._animationTimer)}attachComponentPortal(t){let e=super.attachComponentPortal(t);return e.location.nativeElement.classList.add("mat-mdc-dialog-component-host"),e}static \u0275fac=(()=>{let t;return function(n){return(t||(t=vt(o)))(n||o)}})();static \u0275cmp=A({type:o,selectors:[["mat-dialog-container"]],hostAttrs:["tabindex","-1",1,"mat-mdc-dialog-container","mdc-dialog"],hostVars:10,hostBindings:function(e,n){e&2&&(Wt("id",n._config.id),m("aria-modal",n._config.ariaModal)("role",n._config.role)("aria-labelledby",n._config.ariaLabel?null:n._ariaLabelledByQueue[0])("aria-label",n._config.ariaLabel)("aria-describedby",n._config.ariaDescribedBy||null),O("_mat-animation-noopable",!n._animationsEnabled)("mat-mdc-dialog-container-with-actions",n._actionSectionCount>0))},features:[Z],decls:3,vars:0,consts:[[1,"mat-mdc-dialog-inner-container","mdc-dialog__container"],[1,"mat-mdc-dialog-surface","mdc-dialog__surface"],["cdkPortalOutlet",""]],template:function(e,n){e&1&&(v(0,"div",0)(1,"div",1),Y(2,Dn,0,0,"ng-template",2),w()())},dependencies:[ct],styles:[`.mat-mdc-dialog-container {
  width: 100%;
  height: 100%;
  display: block;
  box-sizing: border-box;
  max-height: inherit;
  min-height: inherit;
  min-width: inherit;
  max-width: inherit;
  outline: 0;
}

.cdk-overlay-pane.mat-mdc-dialog-panel {
  max-width: var(--mat-dialog-container-max-width, 560px);
  min-width: var(--mat-dialog-container-min-width, 280px);
}
@media (max-width: 599px) {
  .cdk-overlay-pane.mat-mdc-dialog-panel {
    max-width: var(--mat-dialog-container-small-max-width, calc(100vw - 32px));
  }
}

.mat-mdc-dialog-inner-container {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-around;
  box-sizing: border-box;
  height: 100%;
  opacity: 0;
  transition: opacity linear var(--mat-dialog-transition-duration, 0ms);
  max-height: inherit;
  min-height: inherit;
  min-width: inherit;
  max-width: inherit;
}
.mdc-dialog--closing .mat-mdc-dialog-inner-container {
  transition: opacity 75ms linear;
  transform: none;
}
.mdc-dialog--open .mat-mdc-dialog-inner-container {
  opacity: 1;
}
._mat-animation-noopable .mat-mdc-dialog-inner-container {
  transition: none;
}

.mat-mdc-dialog-surface {
  display: flex;
  flex-direction: column;
  flex-grow: 0;
  flex-shrink: 0;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  position: relative;
  overflow-y: auto;
  outline: 0;
  transform: scale(0.8);
  transition: transform var(--mat-dialog-transition-duration, 0ms) cubic-bezier(0, 0, 0.2, 1);
  max-height: inherit;
  min-height: inherit;
  min-width: inherit;
  max-width: inherit;
  box-shadow: var(--mat-dialog-container-elevation-shadow, none);
  border-radius: var(--mat-dialog-container-shape, var(--mat-sys-corner-extra-large, 4px));
  background-color: var(--mat-dialog-container-color, var(--mat-sys-surface, white));
}
[dir=rtl] .mat-mdc-dialog-surface {
  text-align: right;
}
.mdc-dialog--open .mat-mdc-dialog-surface, .mdc-dialog--closing .mat-mdc-dialog-surface {
  transform: none;
}
._mat-animation-noopable .mat-mdc-dialog-surface {
  transition: none;
}
.mat-mdc-dialog-surface::before {
  position: absolute;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
  border: 2px solid transparent;
  border-radius: inherit;
  content: "";
  pointer-events: none;
}

.mat-mdc-dialog-title {
  display: block;
  position: relative;
  flex-shrink: 0;
  box-sizing: border-box;
  margin: 0 0 1px;
  padding: var(--mat-dialog-headline-padding, 6px 24px 13px);
}
.mat-mdc-dialog-title::before {
  display: inline-block;
  width: 0;
  height: 40px;
  content: "";
  vertical-align: 0;
}
[dir=rtl] .mat-mdc-dialog-title {
  text-align: right;
}
.mat-mdc-dialog-container .mat-mdc-dialog-title {
  color: var(--mat-dialog-subhead-color, var(--mat-sys-on-surface, rgba(0, 0, 0, 0.87)));
  font-family: var(--mat-dialog-subhead-font, var(--mat-sys-headline-small-font, inherit));
  line-height: var(--mat-dialog-subhead-line-height, var(--mat-sys-headline-small-line-height, 1.5rem));
  font-size: var(--mat-dialog-subhead-size, var(--mat-sys-headline-small-size, 1rem));
  font-weight: var(--mat-dialog-subhead-weight, var(--mat-sys-headline-small-weight, 400));
  letter-spacing: var(--mat-dialog-subhead-tracking, var(--mat-sys-headline-small-tracking, 0.03125em));
}

.mat-mdc-dialog-content {
  display: block;
  flex-grow: 1;
  box-sizing: border-box;
  margin: 0;
  overflow: auto;
  max-height: 65vh;
}
.mat-mdc-dialog-content > :first-child {
  margin-top: 0;
}
.mat-mdc-dialog-content > :last-child {
  margin-bottom: 0;
}
.mat-mdc-dialog-container .mat-mdc-dialog-content {
  color: var(--mat-dialog-supporting-text-color, var(--mat-sys-on-surface-variant, rgba(0, 0, 0, 0.6)));
  font-family: var(--mat-dialog-supporting-text-font, var(--mat-sys-body-medium-font, inherit));
  line-height: var(--mat-dialog-supporting-text-line-height, var(--mat-sys-body-medium-line-height, 1.5rem));
  font-size: var(--mat-dialog-supporting-text-size, var(--mat-sys-body-medium-size, 1rem));
  font-weight: var(--mat-dialog-supporting-text-weight, var(--mat-sys-body-medium-weight, 400));
  letter-spacing: var(--mat-dialog-supporting-text-tracking, var(--mat-sys-body-medium-tracking, 0.03125em));
}
.mat-mdc-dialog-container .mat-mdc-dialog-content {
  padding: var(--mat-dialog-content-padding, 20px 24px);
}
.mat-mdc-dialog-container-with-actions .mat-mdc-dialog-content {
  padding: var(--mat-dialog-with-actions-content-padding, 20px 24px 0);
}
.mat-mdc-dialog-container .mat-mdc-dialog-title + .mat-mdc-dialog-content {
  padding-top: 0;
}

.mat-mdc-dialog-actions {
  display: flex;
  position: relative;
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: center;
  box-sizing: border-box;
  min-height: 52px;
  margin: 0;
  border-top: 1px solid transparent;
  padding: var(--mat-dialog-actions-padding, 16px 24px);
  justify-content: var(--mat-dialog-actions-alignment, flex-end);
}
@media (forced-colors: active) {
  .mat-mdc-dialog-actions {
    border-top-color: CanvasText;
  }
}
.mat-mdc-dialog-actions.mat-mdc-dialog-actions-align-start, .mat-mdc-dialog-actions[align=start] {
  justify-content: start;
}
.mat-mdc-dialog-actions.mat-mdc-dialog-actions-align-center, .mat-mdc-dialog-actions[align=center] {
  justify-content: center;
}
.mat-mdc-dialog-actions.mat-mdc-dialog-actions-align-end, .mat-mdc-dialog-actions[align=end] {
  justify-content: flex-end;
}
.mat-mdc-dialog-actions .mat-button-base + .mat-button-base,
.mat-mdc-dialog-actions .mat-mdc-button-base + .mat-mdc-button-base {
  margin-left: 8px;
}
[dir=rtl] .mat-mdc-dialog-actions .mat-button-base + .mat-button-base,
[dir=rtl] .mat-mdc-dialog-actions .mat-mdc-button-base + .mat-mdc-button-base {
  margin-left: 0;
  margin-right: 8px;
}

.mat-mdc-dialog-component-host {
  display: contents;
}
`],encapsulation:2})}return o})(),Xe="--mat-dialog-transition-duration";function tn(o){return o==null?null:typeof o=="number"?o:o.endsWith("ms")?$t(o.substring(0,o.length-2)):o.endsWith("s")?$t(o.substring(0,o.length-1))*1e3:o==="0"?0:null}var Lt=(function(o){return o[o.OPEN=0]="OPEN",o[o.CLOSING=1]="CLOSING",o[o.CLOSED=2]="CLOSED",o})(Lt||{}),gt=class{_ref;_config;_containerInstance;componentInstance;componentRef=null;disableClose;id;_afterOpened=new Vt(1);_beforeClosed=new Vt(1);_result;_closeFallbackTimeout;_state=Lt.OPEN;_closeInteractionType;constructor(s,t,e){this._ref=s,this._config=t,this._containerInstance=e,this.disableClose=t.disableClose,this.id=s.id,s.addPanelClass("mat-mdc-dialog-panel"),e._animationStateChanged.pipe(rt(n=>n.state==="opened"),N(1)).subscribe(()=>{this._afterOpened.next(),this._afterOpened.complete()}),e._animationStateChanged.pipe(rt(n=>n.state==="closed"),N(1)).subscribe(()=>{clearTimeout(this._closeFallbackTimeout),this._finishDialogClose()}),s.overlayRef.detachments().subscribe(()=>{this._beforeClosed.next(this._result),this._beforeClosed.complete(),this._finishDialogClose()}),ie(this.backdropClick(),this.keydownEvents().pipe(rt(n=>n.keyCode===27&&!this.disableClose&&!nt(n)))).subscribe(n=>{this.disableClose||(n.preventDefault(),en(this,n.type==="keydown"?"keyboard":"mouse"))})}close(s){let t=this._config.closePredicate;t&&!t(s,this._config,this.componentInstance)||(this._result=s,this._containerInstance._animationStateChanged.pipe(rt(e=>e.state==="closing"),N(1)).subscribe(e=>{this._beforeClosed.next(s),this._beforeClosed.complete(),this._ref.overlayRef.detachBackdrop(),this._closeFallbackTimeout=setTimeout(()=>this._finishDialogClose(),e.totalTime+100)}),this._state=Lt.CLOSING,this._containerInstance._startExitAnimation())}afterOpened(){return this._afterOpened}afterClosed(){return this._ref.closed}beforeClosed(){return this._beforeClosed}backdropClick(){return this._ref.backdropClick}keydownEvents(){return this._ref.keydownEvents}updatePosition(s){let t=this._ref.config.positionStrategy;return s&&(s.left||s.right)?s.left?t.left(s.left):t.right(s.right):t.centerHorizontally(),s&&(s.top||s.bottom)?s.top?t.top(s.top):t.bottom(s.bottom):t.centerVertically(),this._ref.updatePosition(),this}updateSize(s="",t=""){return this._ref.updateSize(s,t),this}addPanelClass(s){return this._ref.addPanelClass(s),this}removePanelClass(s){return this._ref.removePanelClass(s),this}getState(){return this._state}_finishDialogClose(){this._state=Lt.CLOSED,this._ref.close(this._result,{focusOrigin:this._closeInteractionType}),this.componentInstance=null}};function en(o,s,t){return o._closeInteractionType=s,o.close(t)}var On=new h("MatMdcDialogData"),Mn=new h("mat-mdc-dialog-default-options"),Fn=new h("mat-mdc-dialog-scroll-strategy",{providedIn:"root",factory:()=>{let o=l(F);return()=>Ot(o)}}),Yt=(()=>{class o{_defaultOptions=l(Mn,{optional:!0});_scrollStrategy=l(Fn);_parentDialog=l(o,{optional:!0,skipSelf:!0});_idGenerator=l(z);_injector=l(F);_dialog=l(Kt);_animationsDisabled=ut();_openDialogsAtThisLevel=[];_afterAllClosedAtThisLevel=new T;_afterOpenedAtThisLevel=new T;dialogConfigClass=Bt;_dialogRefConstructor;_dialogContainerType;_dialogDataToken;get openDialogs(){return this._parentDialog?this._parentDialog.openDialogs:this._openDialogsAtThisLevel}get afterOpened(){return this._parentDialog?this._parentDialog.afterOpened:this._afterOpenedAtThisLevel}_getAfterAllClosed(){let t=this._parentDialog;return t?t._getAfterAllClosed():this._afterAllClosedAtThisLevel}afterAllClosed=ht(()=>this.openDialogs.length?this._getAfterAllClosed():this._getAfterAllClosed().pipe(pt(void 0)));constructor(){this._dialogRefConstructor=gt,this._dialogContainerType=En,this._dialogDataToken=On}open(t,e){let n;e=M(M({},this._defaultOptions||new Bt),e),e.id=e.id||this._idGenerator.getId("mat-mdc-dialog-"),e.scrollStrategy=e.scrollStrategy||this._scrollStrategy();let i=this._dialog.open(t,Xt(M({},e),{positionStrategy:Mt(this._injector).centerHorizontally().centerVertically(),disableClose:!0,closePredicate:void 0,closeOnDestroy:!1,closeOnOverlayDetachments:!1,disableAnimations:this._animationsDisabled||e.enterAnimationDuration?.toLocaleString()==="0"||e.exitAnimationDuration?.toString()==="0",container:{type:this._dialogContainerType,providers:()=>[{provide:this.dialogConfigClass,useValue:e},{provide:G,useValue:e}]},templateContext:()=>({dialogRef:n}),providers:(a,r,d)=>(n=new this._dialogRefConstructor(a,e,d),n.updatePosition(e?.position),[{provide:this._dialogContainerType,useValue:d},{provide:this._dialogDataToken,useValue:r.data},{provide:this._dialogRefConstructor,useValue:n}])}));return n.componentRef=i.componentRef,n.componentInstance=i.componentInstance,this.openDialogs.push(n),this.afterOpened.next(n),n.afterClosed().subscribe(()=>{let a=this.openDialogs.indexOf(n);a>-1&&(this.openDialogs.splice(a,1),this.openDialogs.length||this._getAfterAllClosed().next())}),n}closeAll(){this._closeDialogs(this.openDialogs)}getDialogById(t){return this.openDialogs.find(e=>e.id===t)}ngOnDestroy(){this._closeDialogs(this._openDialogsAtThisLevel),this._afterAllClosedAtThisLevel.complete(),this._afterOpenedAtThisLevel.complete()}_closeDialogs(t){let e=t.length;for(;e--;)t[e].close()}static \u0275fac=function(e){return new(e||o)};static \u0275prov=D({token:o,factory:o.\u0275fac,providedIn:"root"})}return o})(),pi=(()=>{class o{dialogRef=l(gt,{optional:!0});_elementRef=l(I);_dialog=l(Yt);ariaLabel;type="button";dialogResult;_matDialogClose;constructor(){}ngOnInit(){this.dialogRef||(this.dialogRef=on(this._elementRef,this._dialog.openDialogs))}ngOnChanges(t){let e=t._matDialogClose||t._matDialogCloseResult;e&&(this.dialogResult=e.currentValue)}_onButtonClick(t){en(this.dialogRef,t.screenX===0&&t.screenY===0?"keyboard":"mouse",this.dialogResult)}static \u0275fac=function(e){return new(e||o)};static \u0275dir=L({type:o,selectors:[["","mat-dialog-close",""],["","matDialogClose",""]],hostVars:2,hostBindings:function(e,n){e&1&&tt("click",function(a){return n._onButtonClick(a)}),e&2&&m("aria-label",n.ariaLabel||null)("type",n.type)},inputs:{ariaLabel:[0,"aria-label","ariaLabel"],type:"type",dialogResult:[0,"mat-dialog-close","dialogResult"],_matDialogClose:[0,"matDialogClose","_matDialogClose"]},exportAs:["matDialogClose"],features:[de]})}return o})(),nn=(()=>{class o{_dialogRef=l(gt,{optional:!0});_elementRef=l(I);_dialog=l(Yt);constructor(){}ngOnInit(){this._dialogRef||(this._dialogRef=on(this._elementRef,this._dialog.openDialogs)),this._dialogRef&&Promise.resolve().then(()=>{this._onAdd()})}ngOnDestroy(){this._dialogRef?._containerInstance&&Promise.resolve().then(()=>{this._onRemove()})}static \u0275fac=function(e){return new(e||o)};static \u0275dir=L({type:o})}return o})(),fi=(()=>{class o extends nn{id=l(z).getId("mat-mdc-dialog-title-");_onAdd(){this._dialogRef._containerInstance?._addAriaLabelledBy?.(this.id)}_onRemove(){this._dialogRef?._containerInstance?._removeAriaLabelledBy?.(this.id)}static \u0275fac=(()=>{let t;return function(n){return(t||(t=vt(o)))(n||o)}})();static \u0275dir=L({type:o,selectors:[["","mat-dialog-title",""],["","matDialogTitle",""]],hostAttrs:[1,"mat-mdc-dialog-title","mdc-dialog__title"],hostVars:1,hostBindings:function(e,n){e&2&&Wt("id",n.id)},inputs:{id:"id"},exportAs:["matDialogTitle"],features:[Z]})}return o})(),_i=(()=>{class o{static \u0275fac=function(e){return new(e||o)};static \u0275dir=L({type:o,selectors:[["","mat-dialog-content",""],["mat-dialog-content"],["","matDialogContent",""]],hostAttrs:[1,"mat-mdc-dialog-content","mdc-dialog__content"],features:[he([we])]})}return o})(),bi=(()=>{class o extends nn{align;_onAdd(){this._dialogRef._containerInstance?._updateActionSectionCount?.(1)}_onRemove(){this._dialogRef._containerInstance?._updateActionSectionCount?.(-1)}static \u0275fac=(()=>{let t;return function(n){return(t||(t=vt(o)))(n||o)}})();static \u0275dir=L({type:o,selectors:[["","mat-dialog-actions",""],["mat-dialog-actions"],["","matDialogActions",""]],hostAttrs:[1,"mat-mdc-dialog-actions","mdc-dialog__actions"],hostVars:6,hostBindings:function(e,n){e&2&&O("mat-mdc-dialog-actions-align-start",n.align==="start")("mat-mdc-dialog-actions-align-center",n.align==="center")("mat-mdc-dialog-actions-align-end",n.align==="end")},inputs:{align:"align"},features:[Z]})}return o})();function on(o,s){let t=o.nativeElement.parentElement;for(;t&&!t.classList.contains("mat-mdc-dialog-container");)t=t.parentElement;return t?s.find(e=>e.id===t.id):null}var vi=(()=>{class o{static \u0275fac=function(e){return new(e||o)};static \u0275mod=E({type:o});static \u0275inj=x({providers:[Yt],imports:[Ke,Ft,dt,j]})}return o})();var zn=["button"],Gn=["*"];function Hn(o,s){if(o&1&&(v(0,"div",2),X(1,"mat-pseudo-checkbox",6),w()),o&2){let t=Ct();k(),B("disabled",t.disabled)}}var an=new h("MAT_BUTTON_TOGGLE_DEFAULT_OPTIONS",{providedIn:"root",factory:()=>({hideSingleSelectionIndicator:!1,hideMultipleSelectionIndicator:!1,disabledInteractive:!1})}),rn=new h("MatButtonToggleGroup"),Vn={provide:Me,useExisting:se(()=>Un),multi:!0},jt=class{source;value;constructor(s,t){this.source=s,this.value=t}},Un=(()=>{class o{_changeDetector=l(st);_dir=l(lt,{optional:!0});_multiple=!1;_disabled=!1;_disabledInteractive=!1;_selectionModel;_rawValue;_controlValueAccessorChangeFn=()=>{};_onTouched=()=>{};_buttonToggles;appearance;get name(){return this._name}set name(t){this._name=t,this._markButtonsForCheck()}_name=l(z).getId("mat-button-toggle-group-");vertical=!1;get value(){let t=this._selectionModel?this._selectionModel.selected:[];return this.multiple?t.map(e=>e.value):t[0]?t[0].value:void 0}set value(t){this._setSelectionByValue(t),this.valueChange.emit(this.value)}valueChange=new P;get selected(){let t=this._selectionModel?this._selectionModel.selected:[];return this.multiple?t:t[0]||null}get multiple(){return this._multiple}set multiple(t){this._multiple=t,this._markButtonsForCheck()}get disabled(){return this._disabled}set disabled(t){this._disabled=t,this._markButtonsForCheck()}get disabledInteractive(){return this._disabledInteractive}set disabledInteractive(t){this._disabledInteractive=t,this._markButtonsForCheck()}get dir(){return this._dir&&this._dir.value==="rtl"?"rtl":"ltr"}change=new P;get hideSingleSelectionIndicator(){return this._hideSingleSelectionIndicator}set hideSingleSelectionIndicator(t){this._hideSingleSelectionIndicator=t,this._markButtonsForCheck()}_hideSingleSelectionIndicator;get hideMultipleSelectionIndicator(){return this._hideMultipleSelectionIndicator}set hideMultipleSelectionIndicator(t){this._hideMultipleSelectionIndicator=t,this._markButtonsForCheck()}_hideMultipleSelectionIndicator;constructor(){let t=l(an,{optional:!0});this.appearance=t&&t.appearance?t.appearance:"standard",this._hideSingleSelectionIndicator=t?.hideSingleSelectionIndicator??!1,this._hideMultipleSelectionIndicator=t?.hideMultipleSelectionIndicator??!1}ngOnInit(){this._selectionModel=new ze(this.multiple,void 0,!1)}ngAfterContentInit(){this._selectionModel.select(...this._buttonToggles.filter(t=>t.checked)),this.multiple||this._initializeTabIndex()}writeValue(t){this.value=t,this._changeDetector.markForCheck()}registerOnChange(t){this._controlValueAccessorChangeFn=t}registerOnTouched(t){this._onTouched=t}setDisabledState(t){this.disabled=t}_keydown(t){if(this.multiple||this.disabled||nt(t))return;let n=t.target.id,i=this._buttonToggles.toArray().findIndex(r=>r.buttonId===n),a=null;switch(t.keyCode){case 32:case 13:a=this._buttonToggles.get(i)||null;break;case 38:a=this._getNextButton(i,-1);break;case 37:a=this._getNextButton(i,this.dir==="ltr"?-1:1);break;case 40:a=this._getNextButton(i,1);break;case 39:a=this._getNextButton(i,this.dir==="ltr"?1:-1);break;default:return}a&&(t.preventDefault(),a._onButtonClick(),a.focus())}_emitChangeEvent(t){let e=new jt(t,this.value);this._rawValue=e.value,this._controlValueAccessorChangeFn(e.value),this.change.emit(e)}_syncButtonToggle(t,e,n=!1,i=!1){!this.multiple&&this.selected&&!t.checked&&(this.selected.checked=!1),this._selectionModel?e?this._selectionModel.select(t):this._selectionModel.deselect(t):i=!0,i?Promise.resolve().then(()=>this._updateModelValue(t,n)):this._updateModelValue(t,n)}_isSelected(t){return this._selectionModel&&this._selectionModel.isSelected(t)}_isPrechecked(t){return typeof this._rawValue>"u"?!1:this.multiple&&Array.isArray(this._rawValue)?this._rawValue.some(e=>t.value!=null&&e===t.value):t.value===this._rawValue}_initializeTabIndex(){if(this._buttonToggles.forEach(t=>{t.tabIndex=-1}),this.selected)this.selected.tabIndex=0;else for(let t=0;t<this._buttonToggles.length;t++){let e=this._buttonToggles.get(t);if(!e.disabled){e.tabIndex=0;break}}}_getNextButton(t,e){let n=this._buttonToggles;for(let i=1;i<=n.length;i++){let a=(t+e*i+n.length)%n.length,r=n.get(a);if(r&&!r.disabled)return r}return null}_setSelectionByValue(t){if(this._rawValue=t,!this._buttonToggles)return;let e=this._buttonToggles.toArray();if(this.multiple&&t?(Array.isArray(t),this._clearSelection(),t.forEach(n=>this._selectValue(n,e))):(this._clearSelection(),this._selectValue(t,e)),!this.multiple&&e.every(n=>n.tabIndex===-1)){for(let n of e)if(!n.disabled){n.tabIndex=0;break}}}_clearSelection(){this._selectionModel.clear(),this._buttonToggles.forEach(t=>{t.checked=!1,this.multiple||(t.tabIndex=-1)})}_selectValue(t,e){for(let n of e)if(n.value===t){n.checked=!0,this._selectionModel.select(n),this.multiple||(n.tabIndex=0);break}}_updateModelValue(t,e){e&&this._emitChangeEvent(t),this.valueChange.emit(this.value)}_markButtonsForCheck(){this._buttonToggles?.forEach(t=>t._markForCheck())}static \u0275fac=function(e){return new(e||o)};static \u0275dir=L({type:o,selectors:[["mat-button-toggle-group"]],contentQueries:function(e,n,i){if(e&1&&_e(i,sn,5),e&2){let a;U(a=W())&&(n._buttonToggles=a)}},hostAttrs:[1,"mat-button-toggle-group"],hostVars:6,hostBindings:function(e,n){e&1&&tt("keydown",function(a){return n._keydown(a)}),e&2&&(m("role",n.multiple?"group":"radiogroup")("aria-disabled",n.disabled),O("mat-button-toggle-vertical",n.vertical)("mat-button-toggle-group-appearance-standard",n.appearance==="standard"))},inputs:{appearance:"appearance",name:"name",vertical:[2,"vertical","vertical",y],value:"value",multiple:[2,"multiple","multiple",y],disabled:[2,"disabled","disabled",y],disabledInteractive:[2,"disabledInteractive","disabledInteractive",y],hideSingleSelectionIndicator:[2,"hideSingleSelectionIndicator","hideSingleSelectionIndicator",y],hideMultipleSelectionIndicator:[2,"hideMultipleSelectionIndicator","hideMultipleSelectionIndicator",y]},outputs:{valueChange:"valueChange",change:"change"},exportAs:["matButtonToggleGroup"],features:[be([Vn,{provide:rn,useExisting:o}])]})}return o})(),sn=(()=>{class o{_changeDetectorRef=l(st);_elementRef=l(I);_focusMonitor=l(Rt);_idGenerator=l(z);_animationDisabled=ut();_checked=!1;ariaLabel;ariaLabelledby=null;_buttonElement;buttonToggleGroup;get buttonId(){return`${this.id}-button`}id;name;value;get tabIndex(){return this._tabIndex()}set tabIndex(t){this._tabIndex.set(t)}_tabIndex;disableRipple=!1;get appearance(){return this.buttonToggleGroup?this.buttonToggleGroup.appearance:this._appearance}set appearance(t){this._appearance=t}_appearance;get checked(){return this.buttonToggleGroup?this.buttonToggleGroup._isSelected(this):this._checked}set checked(t){t!==this._checked&&(this._checked=t,this.buttonToggleGroup&&this.buttonToggleGroup._syncButtonToggle(this,this._checked),this._changeDetectorRef.markForCheck())}get disabled(){return this._disabled||this.buttonToggleGroup&&this.buttonToggleGroup.disabled}set disabled(t){this._disabled=t}_disabled=!1;get disabledInteractive(){return this._disabledInteractive||this.buttonToggleGroup!==null&&this.buttonToggleGroup.disabledInteractive}set disabledInteractive(t){this._disabledInteractive=t}_disabledInteractive;change=new P;constructor(){l(Ie).load(Be);let t=l(rn,{optional:!0}),e=l(new Dt("tabindex"),{optional:!0})||"",n=l(an,{optional:!0});this._tabIndex=bt(parseInt(e)||0),this.buttonToggleGroup=t,this._appearance=n&&n.appearance?n.appearance:"standard",this._disabledInteractive=n?.disabledInteractive??!1}ngOnInit(){let t=this.buttonToggleGroup;this.id=this.id||this._idGenerator.getId("mat-button-toggle-"),t&&(t._isPrechecked(this)?this.checked=!0:t._isSelected(this)!==this._checked&&t._syncButtonToggle(this,this._checked))}ngAfterViewInit(){this._animationDisabled||this._elementRef.nativeElement.classList.add("mat-button-toggle-animations-enabled"),this._focusMonitor.monitor(this._elementRef,!0)}ngOnDestroy(){let t=this.buttonToggleGroup;this._focusMonitor.stopMonitoring(this._elementRef),t&&t._isSelected(this)&&t._syncButtonToggle(this,!1,!1,!0)}focus(t){this._buttonElement.nativeElement.focus(t)}_onButtonClick(){if(this.disabled)return;let t=this.isSingleSelector()?!0:!this._checked;if(t!==this._checked&&(this._checked=t,this.buttonToggleGroup&&(this.buttonToggleGroup._syncButtonToggle(this,this._checked,!0),this.buttonToggleGroup._onTouched())),this.isSingleSelector()){let e=this.buttonToggleGroup._buttonToggles.find(n=>n.tabIndex===0);e&&(e.tabIndex=-1),this.tabIndex=0}this.change.emit(new jt(this,this.value))}_markForCheck(){this._changeDetectorRef.markForCheck()}_getButtonName(){return this.isSingleSelector()?this.buttonToggleGroup.name:this.name||null}isSingleSelector(){return this.buttonToggleGroup&&!this.buttonToggleGroup.multiple}static \u0275fac=function(e){return new(e||o)};static \u0275cmp=A({type:o,selectors:[["mat-button-toggle"]],viewQuery:function(e,n){if(e&1&&et(zn,5),e&2){let i;U(i=W())&&(n._buttonElement=i.first)}},hostAttrs:["role","presentation",1,"mat-button-toggle"],hostVars:14,hostBindings:function(e,n){e&1&&tt("focus",function(){return n.focus()}),e&2&&(m("aria-label",null)("aria-labelledby",null)("id",n.id)("name",null),O("mat-button-toggle-standalone",!n.buttonToggleGroup)("mat-button-toggle-checked",n.checked)("mat-button-toggle-disabled",n.disabled)("mat-button-toggle-disabled-interactive",n.disabledInteractive)("mat-button-toggle-appearance-standard",n.appearance==="standard"))},inputs:{ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"],id:"id",name:"name",value:"value",tabIndex:"tabIndex",disableRipple:[2,"disableRipple","disableRipple",y],appearance:"appearance",checked:[2,"checked","checked",y],disabled:[2,"disabled","disabled",y],disabledInteractive:[2,"disabledInteractive","disabledInteractive",y]},outputs:{change:"change"},exportAs:["matButtonToggle"],ngContentSelectors:Gn,decls:7,vars:13,consts:[["button",""],["type","button",1,"mat-button-toggle-button","mat-focus-indicator",3,"click","id","disabled"],[1,"mat-button-toggle-checkbox-wrapper"],[1,"mat-button-toggle-label-content"],[1,"mat-button-toggle-focus-overlay"],["matRipple","",1,"mat-button-toggle-ripple",3,"matRippleTrigger","matRippleDisabled"],["state","checked","aria-hidden","true","appearance","minimal",3,"disabled"]],template:function(e,n){if(e&1&&(St(),v(0,"button",1,0),tt("click",function(){return n._onButtonClick()}),pe(2,Hn,2,1,"div",2),v(3,"span",3),It(4),w()(),X(5,"span",4)(6,"span",5)),e&2){let i=kt(1);B("id",n.buttonId)("disabled",n.disabled&&!n.disabledInteractive||null),m("role",n.isSingleSelector()?"radio":"button")("tabindex",n.disabled&&!n.disabledInteractive?-1:n.tabIndex)("aria-pressed",n.isSingleSelector()?null:n.checked)("aria-checked",n.isSingleSelector()?n.checked:null)("name",n._getButtonName())("aria-label",n.ariaLabel)("aria-labelledby",n.ariaLabelledby)("aria-disabled",n.disabled&&n.disabledInteractive?"true":null),k(2),fe(n.buttonToggleGroup&&(!n.buttonToggleGroup.multiple&&!n.buttonToggleGroup.hideSingleSelectionIndicator||n.buttonToggleGroup.multiple&&!n.buttonToggleGroup.hideMultipleSelectionIndicator)?2:-1),k(4),B("matRippleTrigger",i)("matRippleDisabled",n.disableRipple||n.disabled)}},dependencies:[Le,Ge],styles:[`.mat-button-toggle-standalone,
.mat-button-toggle-group {
  position: relative;
  display: inline-flex;
  flex-direction: row;
  white-space: nowrap;
  overflow: hidden;
  -webkit-tap-highlight-color: transparent;
  border-radius: var(--mat-button-toggle-legacy-shape);
  transform: translateZ(0);
}
.mat-button-toggle-standalone:not([class*=mat-elevation-z]),
.mat-button-toggle-group:not([class*=mat-elevation-z]) {
  box-shadow: 0px 3px 1px -2px rgba(0, 0, 0, 0.2), 0px 2px 2px 0px rgba(0, 0, 0, 0.14), 0px 1px 5px 0px rgba(0, 0, 0, 0.12);
}
@media (forced-colors: active) {
  .mat-button-toggle-standalone,
  .mat-button-toggle-group {
    outline: solid 1px;
  }
}

.mat-button-toggle-standalone.mat-button-toggle-appearance-standard,
.mat-button-toggle-group-appearance-standard {
  border-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
  border: solid 1px var(--mat-button-toggle-divider-color, var(--mat-sys-outline));
}
.mat-button-toggle-standalone.mat-button-toggle-appearance-standard .mat-pseudo-checkbox,
.mat-button-toggle-group-appearance-standard .mat-pseudo-checkbox {
  --mat-pseudo-checkbox-minimal-selected-checkmark-color: var(--mat-button-toggle-selected-state-text-color, var(--mat-sys-on-secondary-container));
}
.mat-button-toggle-standalone.mat-button-toggle-appearance-standard:not([class*=mat-elevation-z]),
.mat-button-toggle-group-appearance-standard:not([class*=mat-elevation-z]) {
  box-shadow: none;
}
@media (forced-colors: active) {
  .mat-button-toggle-standalone.mat-button-toggle-appearance-standard,
  .mat-button-toggle-group-appearance-standard {
    outline: 0;
  }
}

.mat-button-toggle-vertical {
  flex-direction: column;
}
.mat-button-toggle-vertical .mat-button-toggle-label-content {
  display: block;
}

.mat-button-toggle {
  white-space: nowrap;
  position: relative;
  color: var(--mat-button-toggle-legacy-text-color);
  font-family: var(--mat-button-toggle-legacy-label-text-font);
  font-size: var(--mat-button-toggle-legacy-label-text-size);
  line-height: var(--mat-button-toggle-legacy-label-text-line-height);
  font-weight: var(--mat-button-toggle-legacy-label-text-weight);
  letter-spacing: var(--mat-button-toggle-legacy-label-text-tracking);
  --mat-pseudo-checkbox-minimal-selected-checkmark-color: var(--mat-button-toggle-legacy-selected-state-text-color);
}
.mat-button-toggle.cdk-keyboard-focused .mat-button-toggle-focus-overlay {
  opacity: var(--mat-button-toggle-legacy-focus-state-layer-opacity);
}
.mat-button-toggle .mat-icon svg {
  vertical-align: top;
}

.mat-button-toggle-checkbox-wrapper {
  display: inline-block;
  justify-content: flex-start;
  align-items: center;
  width: 0;
  height: 18px;
  line-height: 18px;
  overflow: hidden;
  box-sizing: border-box;
  position: absolute;
  top: 50%;
  left: 16px;
  transform: translate3d(0, -50%, 0);
}
[dir=rtl] .mat-button-toggle-checkbox-wrapper {
  left: auto;
  right: 16px;
}
.mat-button-toggle-appearance-standard .mat-button-toggle-checkbox-wrapper {
  left: 12px;
}
[dir=rtl] .mat-button-toggle-appearance-standard .mat-button-toggle-checkbox-wrapper {
  left: auto;
  right: 12px;
}
.mat-button-toggle-checked .mat-button-toggle-checkbox-wrapper {
  width: 18px;
}
.mat-button-toggle-animations-enabled .mat-button-toggle-checkbox-wrapper {
  transition: width 150ms 45ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mat-button-toggle-vertical .mat-button-toggle-checkbox-wrapper {
  transition: none;
}

.mat-button-toggle-checked {
  color: var(--mat-button-toggle-legacy-selected-state-text-color);
  background-color: var(--mat-button-toggle-legacy-selected-state-background-color);
}

.mat-button-toggle-disabled {
  pointer-events: none;
  color: var(--mat-button-toggle-legacy-disabled-state-text-color);
  background-color: var(--mat-button-toggle-legacy-disabled-state-background-color);
  --mat-pseudo-checkbox-minimal-disabled-selected-checkmark-color: var(--mat-button-toggle-legacy-disabled-state-text-color);
}
.mat-button-toggle-disabled.mat-button-toggle-checked {
  background-color: var(--mat-button-toggle-legacy-disabled-selected-state-background-color);
}

.mat-button-toggle-disabled-interactive {
  pointer-events: auto;
}

.mat-button-toggle-appearance-standard {
  color: var(--mat-button-toggle-text-color, var(--mat-sys-on-surface));
  background-color: var(--mat-button-toggle-background-color, transparent);
  font-family: var(--mat-button-toggle-label-text-font, var(--mat-sys-label-large-font));
  font-size: var(--mat-button-toggle-label-text-size, var(--mat-sys-label-large-size));
  line-height: var(--mat-button-toggle-label-text-line-height, var(--mat-sys-label-large-line-height));
  font-weight: var(--mat-button-toggle-label-text-weight, var(--mat-sys-label-large-weight));
  letter-spacing: var(--mat-button-toggle-label-text-tracking, var(--mat-sys-label-large-tracking));
}
.mat-button-toggle-group-appearance-standard .mat-button-toggle-appearance-standard + .mat-button-toggle-appearance-standard {
  border-left: solid 1px var(--mat-button-toggle-divider-color, var(--mat-sys-outline));
}
[dir=rtl] .mat-button-toggle-group-appearance-standard .mat-button-toggle-appearance-standard + .mat-button-toggle-appearance-standard {
  border-left: none;
  border-right: solid 1px var(--mat-button-toggle-divider-color, var(--mat-sys-outline));
}
.mat-button-toggle-group-appearance-standard.mat-button-toggle-vertical .mat-button-toggle-appearance-standard + .mat-button-toggle-appearance-standard {
  border-left: none;
  border-right: none;
  border-top: solid 1px var(--mat-button-toggle-divider-color, var(--mat-sys-outline));
}
.mat-button-toggle-appearance-standard.mat-button-toggle-checked {
  color: var(--mat-button-toggle-selected-state-text-color, var(--mat-sys-on-secondary-container));
  background-color: var(--mat-button-toggle-selected-state-background-color, var(--mat-sys-secondary-container));
}
.mat-button-toggle-appearance-standard.mat-button-toggle-disabled {
  color: var(--mat-button-toggle-disabled-state-text-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
  background-color: var(--mat-button-toggle-disabled-state-background-color, transparent);
}
.mat-button-toggle-appearance-standard.mat-button-toggle-disabled .mat-pseudo-checkbox {
  --mat-pseudo-checkbox-minimal-disabled-selected-checkmark-color: var(--mat-button-toggle-disabled-selected-state-text-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mat-button-toggle-appearance-standard.mat-button-toggle-disabled.mat-button-toggle-checked {
  color: var(--mat-button-toggle-disabled-selected-state-text-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
  background-color: var(--mat-button-toggle-disabled-selected-state-background-color, color-mix(in srgb, var(--mat-sys-on-surface) 12%, transparent));
}
.mat-button-toggle-appearance-standard .mat-button-toggle-focus-overlay {
  background-color: var(--mat-button-toggle-state-layer-color, var(--mat-sys-on-surface));
}
.mat-button-toggle-appearance-standard:hover .mat-button-toggle-focus-overlay {
  opacity: var(--mat-button-toggle-hover-state-layer-opacity, var(--mat-sys-hover-state-layer-opacity));
}
.mat-button-toggle-appearance-standard.cdk-keyboard-focused .mat-button-toggle-focus-overlay {
  opacity: var(--mat-button-toggle-focus-state-layer-opacity, var(--mat-sys-focus-state-layer-opacity));
}
@media (hover: none) {
  .mat-button-toggle-appearance-standard:hover .mat-button-toggle-focus-overlay {
    display: none;
  }
}

.mat-button-toggle-label-content {
  -webkit-user-select: none;
  user-select: none;
  display: inline-block;
  padding: 0 16px;
  line-height: var(--mat-button-toggle-legacy-height);
  position: relative;
}
.mat-button-toggle-appearance-standard .mat-button-toggle-label-content {
  padding: 0 12px;
  line-height: var(--mat-button-toggle-height, 40px);
}

.mat-button-toggle-label-content > * {
  vertical-align: middle;
}

.mat-button-toggle-focus-overlay {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  border-radius: inherit;
  pointer-events: none;
  opacity: 0;
  background-color: var(--mat-button-toggle-legacy-state-layer-color);
}

@media (forced-colors: active) {
  .mat-button-toggle-checked .mat-button-toggle-focus-overlay {
    border-bottom: solid 500px;
    opacity: 0.5;
    height: 0;
  }
  .mat-button-toggle-checked:hover .mat-button-toggle-focus-overlay {
    opacity: 0.6;
  }
  .mat-button-toggle-checked.mat-button-toggle-appearance-standard .mat-button-toggle-focus-overlay {
    border-bottom: solid 500px;
  }
}
.mat-button-toggle .mat-button-toggle-ripple {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  pointer-events: none;
}

.mat-button-toggle-button {
  border: 0;
  background: none;
  color: inherit;
  padding: 0;
  margin: 0;
  font: inherit;
  outline: none;
  width: 100%;
  cursor: pointer;
}
.mat-button-toggle-animations-enabled .mat-button-toggle-button {
  transition: padding 150ms 45ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mat-button-toggle-vertical .mat-button-toggle-button {
  transition: none;
}
.mat-button-toggle-disabled .mat-button-toggle-button {
  cursor: default;
}
.mat-button-toggle-button::-moz-focus-inner {
  border: 0;
}
.mat-button-toggle-checked .mat-button-toggle-button:has(.mat-button-toggle-checkbox-wrapper) {
  padding-left: 30px;
}
[dir=rtl] .mat-button-toggle-checked .mat-button-toggle-button:has(.mat-button-toggle-checkbox-wrapper) {
  padding-left: 0;
  padding-right: 30px;
}

.mat-button-toggle-standalone.mat-button-toggle-appearance-standard {
  --mat-focus-indicator-border-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
}

.mat-button-toggle-group-appearance-standard:not(.mat-button-toggle-vertical) .mat-button-toggle:last-of-type .mat-button-toggle-button::before {
  border-top-right-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
  border-bottom-right-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
}
.mat-button-toggle-group-appearance-standard:not(.mat-button-toggle-vertical) .mat-button-toggle:first-of-type .mat-button-toggle-button::before {
  border-top-left-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
  border-bottom-left-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
}

.mat-button-toggle-group-appearance-standard.mat-button-toggle-vertical .mat-button-toggle:last-of-type .mat-button-toggle-button::before {
  border-bottom-right-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
  border-bottom-left-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
}
.mat-button-toggle-group-appearance-standard.mat-button-toggle-vertical .mat-button-toggle:first-of-type .mat-button-toggle-button::before {
  border-top-right-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
  border-top-left-radius: var(--mat-button-toggle-shape, var(--mat-sys-corner-extra-large));
}
`],encapsulation:2,changeDetection:0})}return o})(),Vi=(()=>{class o{static \u0275fac=function(e){return new(e||o)};static \u0275mod=E({type:o});static \u0275inj=x({imports:[je,sn,j]})}return o})();function Wn(o){return o.metadata&&(typeof o.metadata=="string"?JSON.parse(o.metadata):o.metadata).copilot_mode||null}function Wi(o){return Wn(o)==="troubleshooting_injection"}var it=(function(o){return o.NETWORK_ERROR="NETWORK_ERROR",o.PROJECT_NOT_OPENED="PROJECT_NOT_OPENED",o.LLM_NOT_CONFIGURED="LLM_NOT_CONFIGURED",o.SESSION_NOT_FOUND="SESSION_NOT_FOUND",o.UNAUTHORIZED="UNAUTHORIZED",o.UNKNOWN_ERROR="UNKNOWN_ERROR",o})(it||{});var zt=class{authToken;id;name;location;host;port;path;ubridge_path;status="stopped";protocol;username;password;tokenExpired=!1};var ln=(()=>{class o{httpController;controllerIds=[];serviceInitialized=new T;isServiceInitialized;constructor(t){this.httpController=t,this.controllerIds=this.getcontrollerIds(),this.isServiceInitialized=!0,this.serviceInitialized.next(this.isServiceInitialized)}getcontrollerIds(){let t=localStorage.getItem("controllerIds");if(t?.length>0){let e=t.split(",");return[...new Set(e)].filter(n=>n&&n.trim().length>0)}return[]}updatecontrollerIds(){localStorage.removeItem("controllerIds"),localStorage.setItem("controllerIds",this.controllerIds.toString())}get(t){let e=JSON.parse(localStorage.getItem(`controller-${t}`));return new Promise(i=>{i(e)})}create(t){if(this.findAllSync().some(r=>r.name===t.name))return Promise.reject(new Error(`Controller with name "${t.name}" already exists`));let n=this.controllerIds.map(r=>parseInt(r.replace("controller-",""),10)).filter(r=>!isNaN(r)),i=n.length>0?Math.max(...n):0;return t.id=i+1,localStorage.setItem(`controller-${t.id}`,JSON.stringify(t)),this.controllerIds.push(`controller-${t.id}`),this.updatecontrollerIds(),new Promise(r=>{r(t)})}findAllSync(){let t=[];return this.controllerIds.forEach(e=>{let n=localStorage.getItem(e);n&&t.push(JSON.parse(n))}),t}isControllerNameTaken(t){return this.findAllSync().some(n=>n.name===t)}update(t){return localStorage.removeItem(`controller-${t.id}`),localStorage.setItem(`controller-${t.id}`,JSON.stringify(t)),new Promise(n=>{n(t)})}findAll(){return new Promise(e=>{let n=[];this.controllerIds.forEach(i=>{let a=localStorage.getItem(i);if(a){let r=JSON.parse(a);n.push(r)}}),e(n)})}delete(t){return localStorage.removeItem(`controller-${t.id}`),this.controllerIds=this.controllerIds.filter(n=>n!==`controller-${t.id}`),this.updatecontrollerIds(),new Promise(n=>{n(t.id)})}getControllerUrl(t){return`${t.protocol}//${t.host}:${t.port}/`}checkControllerVersion(t){return this.httpController.get(t,"/version").pipe(ne(5e3),f(e=>{if(e.name==="TimeoutError"){let n=new Error("Connection timeout");return g(()=>n)}return g(()=>e)}))}getLocalController(t,e){return new Promise((i,a)=>{this.findAll().then(r=>{let d=r.find(c=>c.location==="bundled");if(d)d.host=t,d.port=e,d.protocol=location.protocol,this.update(d).then(c=>{i(c)},a);else{let c=new zt;c.name="local",c.host=t,c.port=e,c.location="bundled",c.protocol=location.protocol,this.create(c).then(C=>{i(C)},a)}},a)})}static \u0275fac=function(e){return new(e||o)(S(Nt))};static \u0275prov=D({token:o,factory:o.\u0275fac})}return o})();var ea=(()=>{class o{http;httpController;controllerService;currentProjectId=null;currentSessionId=null;isStreaming=new ee(!1);constructor(t,e,n){this.http=t,this.httpController=e,this.controllerService=n}injectFault(t,e,n){let i=`${this.getControllerUrl(t)}/v3/copilot/projects/${e}/chat/inject`,a=this.getAuthHeaders(t),r={"Content-Type":"application/json"};return a.keys().forEach(d=>{let c=a.get(d);c&&(r[d]=c)}),new Ht(d=>(fetch(i,{method:"POST",headers:r,body:JSON.stringify({message:n})}).then(async c=>{if(!c.ok){let u=`HTTP error! status: ${c.status}`;try{let b=await c.json();b.message&&(u=b.message)}catch{c.statusText&&(u=c.statusText)}let _=new Error(u);throw _.status=c.status,_.statusText=c.statusText,_.error={message:u},_}if(!c.body)throw new Error("Response body is null");let C=c.body.getReader(),Gt=new TextDecoder,H="";(async()=>{try{for(;;){let{done:u,value:_}=await C.read();if(u){d.complete();break}H+=Gt.decode(_,{stream:!0});let b=H.split(`
`);H=b.pop()||"";for(let at of b)if(at.startsWith("data: ")){let V=at.slice(6).trim();if(V)try{let p=JSON.parse(V);if(p.type==="heartbeat")continue;if(d.next(p),p.type==="done"||p.type==="error"){d.complete();break}}catch(p){console.error("Failed to parse SSE data:",V,p)}}if(d.closed)break}}catch(u){console.error("Stream processing error:",u),d.error(u)}finally{C.cancel()}})()}).catch(c=>{console.error("Fetch error:",c),d.error(c)}),()=>{})).pipe(f(d=>g(()=>d)))}streamChat(t,e,n){this.currentProjectId=e,this.isStreaming.next(!0);let i=`${this.getControllerUrl(t)}/v3/copilot/projects/${e}/chat/stream`,a=this.getAuthHeaders(t),r={"Content-Type":"application/json"};return a.keys().forEach(d=>{let c=a.get(d);c&&(r[d]=c)}),new Ht(d=>(fetch(i,{method:"POST",headers:r,body:JSON.stringify(n)}).then(async c=>{if(!c.ok){let u=`HTTP error! status: ${c.status}`;try{let b=await c.json();b.message&&(u=b.message)}catch{c.statusText&&(u=c.statusText)}let _=new Error(u);throw _.status=c.status,_.statusText=c.statusText,_.error={message:u},_}if(!c.body)throw new Error("Response body is null");let C=c.body.getReader(),Gt=new TextDecoder,H="";(async()=>{try{for(;;){let{done:u,value:_}=await C.read();if(u){d.complete();break}H+=Gt.decode(_,{stream:!0});let b=H.split(`
`);H=b.pop()||"";for(let at of b)if(at.startsWith("data: ")){let V=at.slice(6).trim();if(V)try{let p=JSON.parse(V);if(p.type==="heartbeat")continue;if(p.session_id&&(this.currentSessionId=p.session_id),d.next(p),p.type==="done"||p.type==="error"){d.complete();break}}catch(p){console.error("Failed to parse SSE data:",V,p)}}if(d.closed)break}}catch(u){console.error("Stream processing error:",u),d.error(u)}finally{C.cancel()}})()}).catch(c=>{console.error("Fetch error:",c),d.error(c)}).finally(()=>{this.isStreaming.next(!1)}),()=>{this.isStreaming.next(!1)})).pipe(f(d=>(this.isStreaming.next(!1),g(()=>d))))}getSessions(t,e){return this.httpController.get(t,`/copilot/projects/${e}/chat/sessions`).pipe(f(n=>(console.error("Failed to get sessions:",n),g(()=>n))))}getSessionHistory(t,e,n,i=100){let a=i?{limit:i}:void 0;return this.httpController.get(t,`/copilot/projects/${e}/chat/sessions/${n}/history`).pipe(f(r=>(console.error("Failed to get session history:",r),g(()=>r))))}renameSession(t,e,n,i){let a={title:i};return this.httpController.patch(t,`/copilot/projects/${e}/chat/sessions/${n}`,a).pipe(f(r=>(console.error("Failed to rename session:",r),g(()=>r))))}deleteSession(t,e,n){return this.httpController.delete(t,`/copilot/projects/${e}/chat/sessions/${n}`).pipe(f(i=>(console.error("Failed to delete session:",i),g(()=>i))))}pinSession(t,e,n){return this.httpController.put(t,`/copilot/projects/${e}/chat/sessions/${n}/pin`,null).pipe(f(i=>(console.error("Failed to pin session:",i),g(()=>i))))}unpinSession(t,e,n){return this.httpController.delete(t,`/copilot/projects/${e}/chat/sessions/${n}/pin`).pipe(f(i=>(console.error("Failed to unpin session:",i),g(()=>i))))}getStreamingState(){return this.isStreaming.asObservable()}abortChat(t,e,n){return this.httpController.post(t,`/copilot/projects/${e}/chat/sessions/${n}/abort`,null).pipe(f(i=>(console.error("Failed to abort chat:",i),g(()=>i))))}getCurrentSessionId(){return this.currentSessionId}resetCurrentSession(){this.currentSessionId=null,this.currentProjectId=null}reloadSkills(t){return this.httpController.post(t,"/copilot/reload/skills",null).pipe(f(e=>(console.error("Failed to reload skills:",e),g(()=>e))))}getControllerUrl(t){return`${t.protocol==="https:"?"https":"http"}://${t.host}:${t.port}`}getAuthHeaders(t){let e=new Ce;if(t.authToken)return e.set("Authorization",`Bearer ${t.authToken}`);if(t.username&&t.password){let n=btoa(`${t.username}:${t.password}`);return e.set("Authorization",`Basic ${n}`)}return e}createChatError(t){return t.status===401?{type:it.UNAUTHORIZED,message:"Unauthorized access",details:t}:t.status===404?{type:it.SESSION_NOT_FOUND,message:"Session not found",details:t}:t.message&&t.message.includes("fetch")?{type:it.NETWORK_ERROR,message:"Network connection failed",details:t}:{type:it.UNKNOWN_ERROR,message:t.message||"Unknown error",details:t}}static \u0275fac=function(e){return new(e||o)(S(At),S(Nt),S(ln))};static \u0275prov=D({token:o,factory:o.\u0275fac,providedIn:"root"})}return o})();export{io as a,ao as b,Qe as c,Do as d,xo as e,zt as f,ln as g,Jt as h,kn as i,Kt as j,Ke as k,gt as l,On as m,Yt as n,pi as o,fi as p,_i as q,bi as r,vi as s,Un as t,sn as u,Vi as v,Wi as w,ea as x};
