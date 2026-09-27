import{$ as w,$a as Xt,$c as et,$e as Te,A as lt,Ad as be,Cb as pt,Cd as vt,Db as ht,Ea as y,Eb as F,Ed as _e,F as zt,Fa as qt,Fb as ie,G as X,Ga as Jt,Gc as le,Ge as De,Hd as yt,He as ot,I as b,Ia as Kt,Jd as ve,M as z,Ma as O,Mc as ce,Na as E,Oa as M,Qa as Zt,Ra as W,Rc as de,Sa as $,Sb as oe,Tc as bt,V as ct,Xa as m,Xc as Mt,Xe as Se,Za as Yt,Ze as xe,_ as Ht,_c as ue,a as S,aa as I,ac as ae,b as jt,ba as _,ca as H,da as l,eb as R,ec as re,ef as kt,fb as v,fd as J,ff as we,gb as C,h as It,hb as U,hd as ge,hf as Ie,i as D,j as Gt,ja as Ot,k as At,ka as Wt,la as x,le as Ct,ma as $t,mc as tt,md as P,nb as gt,oa as A,oc as k,od as Rt,pa as Ut,pb as Et,pc as ft,pd as me,qb as Q,qd as pe,ra as dt,s as p,sb as mt,se as ye,ta as Qt,tb as te,td as nt,te as Ce,ua as ut,ub as ee,ud as it,v as Vt,va as T,vb as ne,vd as K,ve as ke,wb as q,wc as se,wd as _t,xb as G,yb as V,yd as he,zd as fe}from"./chunk-G7NALUVX.js";var We=["determinateSpinner"];function $e(i,a){if(i&1&&(Ot(),v(0,"svg",11),U(1,"circle",12),C()),i&2){let t=mt();m("viewBox",t._viewBox()),y(),ht("stroke-dasharray",t._strokeCircumference(),"px")("stroke-dashoffset",t._strokeCircumference()/2,"px")("stroke-width",t._circleStrokeWidth(),"%"),m("r",t._circleRadius())}}var Ue=new _("mat-progress-spinner-default-options",{providedIn:"root",factory:()=>({diameter:Ae})}),Ae=100,Qe=10,En=(()=>{class i{_elementRef=l(T);_noopAnimations;get color(){return this._color||this._defaultColor}set color(t){this._color=t}_color;_defaultColor="primary";_determinateCircle;constructor(){let t=l(Ue),e=De(),n=this._elementRef.nativeElement;this._noopAnimations=e==="di-disabled"&&!!t&&!t._forceAnimations,this.mode=n.nodeName.toLowerCase()==="mat-spinner"?"indeterminate":"determinate",!this._noopAnimations&&e==="reduced-motion"&&n.classList.add("mat-progress-spinner-reduced-motion"),t&&(t.color&&(this.color=this._defaultColor=t.color),t.diameter&&(this.diameter=t.diameter),t.strokeWidth&&(this.strokeWidth=t.strokeWidth))}mode;get value(){return this.mode==="determinate"?this._value:0}set value(t){this._value=Math.max(0,Math.min(100,t||0))}_value=0;get diameter(){return this._diameter}set diameter(t){this._diameter=t||0}_diameter=Ae;get strokeWidth(){return this._strokeWidth??this.diameter/10}set strokeWidth(t){this._strokeWidth=t||0}_strokeWidth;_circleRadius(){return(this.diameter-Qe)/2}_viewBox(){let t=this._circleRadius()*2+this.strokeWidth;return`0 0 ${t} ${t}`}_strokeCircumference(){return 2*Math.PI*this._circleRadius()}_strokeDashOffset(){return this.mode==="determinate"?this._strokeCircumference()*(100-this._value)/100:null}_circleStrokeWidth(){return this.strokeWidth/this.diameter*100}static \u0275fac=function(e){return new(e||i)};static \u0275cmp=O({type:i,selectors:[["mat-progress-spinner"],["mat-spinner"]],viewQuery:function(e,n){if(e&1&&q(We,5),e&2){let o;G(o=V())&&(n._determinateCircle=o.first)}},hostAttrs:["role","progressbar","tabindex","-1",1,"mat-mdc-progress-spinner","mdc-circular-progress"],hostVars:18,hostBindings:function(e,n){e&2&&(m("aria-valuemin",0)("aria-valuemax",100)("aria-valuenow",n.mode==="determinate"?n.value:null)("mode",n.mode),ie("mat-"+n.color),ht("width",n.diameter,"px")("height",n.diameter,"px")("--mat-progress-spinner-size",n.diameter+"px")("--mat-progress-spinner-active-indicator-width",n.diameter+"px"),F("_mat-animation-noopable",n._noopAnimations)("mdc-circular-progress--indeterminate",n.mode==="indeterminate"))},inputs:{color:"color",mode:"mode",value:[2,"value","value",ft],diameter:[2,"diameter","diameter",ft],strokeWidth:[2,"strokeWidth","strokeWidth",ft]},exportAs:["matProgressSpinner"],decls:14,vars:11,consts:[["circle",""],["determinateSpinner",""],["aria-hidden","true",1,"mdc-circular-progress__determinate-container"],["xmlns","http://www.w3.org/2000/svg","focusable","false",1,"mdc-circular-progress__determinate-circle-graphic"],["cx","50%","cy","50%",1,"mdc-circular-progress__determinate-circle"],["aria-hidden","true",1,"mdc-circular-progress__indeterminate-container"],[1,"mdc-circular-progress__spinner-layer"],[1,"mdc-circular-progress__circle-clipper","mdc-circular-progress__circle-left"],[3,"ngTemplateOutlet"],[1,"mdc-circular-progress__gap-patch"],[1,"mdc-circular-progress__circle-clipper","mdc-circular-progress__circle-right"],["xmlns","http://www.w3.org/2000/svg","focusable","false",1,"mdc-circular-progress__indeterminate-circle-graphic"],["cx","50%","cy","50%"]],template:function(e,n){if(e&1&&($(0,$e,2,8,"ng-template",null,0,ae),v(2,"div",2,1),Ot(),v(4,"svg",3),U(5,"circle",4),C()(),Wt(),v(6,"div",5)(7,"div",6)(8,"div",7),gt(9,8),C(),v(10,"div",9),gt(11,8),C(),v(12,"div",10),gt(13,8),C()()()),e&2){let o=pt(1);y(4),m("viewBox",n._viewBox()),y(),ht("stroke-dasharray",n._strokeCircumference(),"px")("stroke-dashoffset",n._strokeDashOffset(),"px")("stroke-width",n._circleStrokeWidth(),"%"),m("r",n._circleRadius()),y(4),R("ngTemplateOutlet",o),y(2),R("ngTemplateOutlet",o),y(2),R("ngTemplateOutlet",o)}},dependencies:[se],styles:[`.mat-mdc-progress-spinner {
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
`],encapsulation:2,changeDetection:0})}return i})();var Mn=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275mod=E({type:i});static \u0275inj=I({imports:[J]})}return i})();function qe(i,a){}var B=class{viewContainerRef;injector;id;role="dialog";panelClass="";hasBackdrop=!0;backdropClass="";disableClose=!1;closePredicate;width="";height="";minWidth;minHeight;maxWidth;maxHeight;positionStrategy;data=null;direction;ariaDescribedBy=null;ariaLabelledBy=null;ariaLabel=null;ariaModal=!1;autoFocus="first-tabbable";restoreFocus=!0;scrollStrategy;closeOnNavigation=!0;closeOnDestroy=!0;closeOnOverlayDetachments=!0;disableAnimations=!1;providers;container;templateContext};var Pt=(()=>{class i extends pe{_elementRef=l(T);_focusTrapFactory=l(Ce);_config;_interactivityChecker=l(ye);_ngZone=l(Ut);_focusMonitor=l(Ct);_renderer=l(Kt);_changeDetectorRef=l(tt);_injector=l(x);_platform=l(ue);_document=l($t);_portalOutlet;_focusTrapped=new D;_focusTrap=null;_elementFocusedBeforeDialogWasOpened=null;_closeInteractionType=null;_ariaLabelledByQueue=[];_isDestroyed=!1;constructor(){super(),this._config=l(B,{optional:!0})||new B,this._config.ariaLabelledBy&&this._ariaLabelledByQueue.push(this._config.ariaLabelledBy)}_addAriaLabelledBy(t){this._ariaLabelledByQueue.push(t),this._changeDetectorRef.markForCheck()}_removeAriaLabelledBy(t){let e=this._ariaLabelledByQueue.indexOf(t);e>-1&&(this._ariaLabelledByQueue.splice(e,1),this._changeDetectorRef.markForCheck())}_contentAttached(){this._initializeFocusTrap(),this._captureInitialFocus()}_captureInitialFocus(){this._trapFocus()}ngOnDestroy(){this._focusTrapped.complete(),this._isDestroyed=!0,this._restoreFocus()}attachComponentPortal(t){this._portalOutlet.hasAttached();let e=this._portalOutlet.attachComponentPortal(t);return this._contentAttached(),e}attachTemplatePortal(t){this._portalOutlet.hasAttached();let e=this._portalOutlet.attachTemplatePortal(t);return this._contentAttached(),e}attachDomPortal=t=>{this._portalOutlet.hasAttached();let e=this._portalOutlet.attachDomPortal(t);return this._contentAttached(),e};_recaptureFocus(){this._containsFocus()||this._trapFocus()}_forceFocus(t,e){this._interactivityChecker.isFocusable(t)||(t.tabIndex=-1,this._ngZone.runOutsideAngular(()=>{let n=()=>{o(),r(),t.removeAttribute("tabindex")},o=this._renderer.listen(t,"blur",n),r=this._renderer.listen(t,"mousedown",n)})),t.focus(e)}_focusByCssSelector(t,e){let n=this._elementRef.nativeElement.querySelector(t);n&&this._forceFocus(n,e)}_trapFocus(t){this._isDestroyed||qt(()=>{let e=this._elementRef.nativeElement;switch(this._config.autoFocus){case!1:case"dialog":this._containsFocus()||e.focus(t);break;case!0:case"first-tabbable":this._focusTrap?.focusInitialElement(t)||this._focusDialogContainer(t);break;case"first-heading":this._focusByCssSelector('h1, h2, h3, h4, h5, h6, [role="heading"]',t);break;default:this._focusByCssSelector(this._config.autoFocus,t);break}this._focusTrapped.next()},{injector:this._injector})}_restoreFocus(){let t=this._config.restoreFocus,e=null;if(typeof t=="string"?e=this._document.querySelector(t):typeof t=="boolean"?e=t?this._elementFocusedBeforeDialogWasOpened:null:t&&(e=t),this._config.restoreFocus&&e&&typeof e.focus=="function"){let n=bt(),o=this._elementRef.nativeElement;(!n||n===this._document.body||n===o||o.contains(n))&&(this._focusMonitor?(this._focusMonitor.focusVia(e,this._closeInteractionType),this._closeInteractionType=null):e.focus())}this._focusTrap&&this._focusTrap.destroy()}_focusDialogContainer(t){this._elementRef.nativeElement.focus?.(t)}_containsFocus(){let t=this._elementRef.nativeElement,e=bt();return t===e||t.contains(e)}_initializeFocusTrap(){this._platform.isBrowser&&(this._focusTrap=this._focusTrapFactory.create(this._elementRef.nativeElement),this._document&&(this._elementFocusedBeforeDialogWasOpened=bt()))}static \u0275fac=function(e){return new(e||i)};static \u0275cmp=O({type:i,selectors:[["cdk-dialog-container"]],viewQuery:function(e,n){if(e&1&&q(nt,7),e&2){let o;G(o=V())&&(n._portalOutlet=o.first)}},hostAttrs:["tabindex","-1",1,"cdk-dialog-container"],hostVars:6,hostBindings:function(e,n){e&2&&m("id",n._config.id||null)("role",n._config.role)("aria-modal",n._config.ariaModal)("aria-labelledby",n._config.ariaLabel?null:n._ariaLabelledByQueue[0])("aria-label",n._config.ariaLabel)("aria-describedby",n._config.ariaDescribedBy||null)},features:[W],decls:1,vars:0,consts:[["cdkPortalOutlet",""]],template:function(e,n){e&1&&$(0,qe,0,0,"ng-template",0)},dependencies:[nt],styles:[`.cdk-dialog-container {
  display: block;
  width: 100%;
  height: 100%;
  min-height: inherit;
  max-height: inherit;
}
`],encapsulation:2})}return i})(),rt=class{overlayRef;config;componentInstance=null;componentRef=null;containerInstance;disableClose;closed=new D;backdropClick;keydownEvents;outsidePointerEvents;id;_detachSubscription;constructor(a,t){this.overlayRef=a,this.config=t,this.disableClose=t.disableClose,this.backdropClick=a.backdropClick(),this.keydownEvents=a.keydownEvents(),this.outsidePointerEvents=a.outsidePointerEvents(),this.id=t.id,this.keydownEvents.subscribe(e=>{e.keyCode===27&&!this.disableClose&&!K(e)&&(e.preventDefault(),this.close(void 0,{focusOrigin:"keyboard"}))}),this.backdropClick.subscribe(()=>{!this.disableClose&&this._canClose()?this.close(void 0,{focusOrigin:"mouse"}):this.containerInstance._recaptureFocus?.()}),this._detachSubscription=a.detachments().subscribe(()=>{t.closeOnOverlayDetachments!==!1&&this.close()})}close(a,t){if(this._canClose(a)){let e=this.closed;this.containerInstance._closeInteractionType=t?.focusOrigin||"program",this._detachSubscription.unsubscribe(),this.overlayRef.dispose(),e.next(a),e.complete(),this.componentInstance=this.containerInstance=null}}updatePosition(){return this.overlayRef.updatePosition(),this}updateSize(a="",t=""){return this.overlayRef.updateSize({width:a,height:t}),this}addPanelClass(a){return this.overlayRef.addPanelClass(a),this}removePanelClass(a){return this.overlayRef.removePanelClass(a),this}_canClose(a){let t=this.config;return!!this.containerInstance&&(!t.closePredicate||t.closePredicate(a,t,this.componentInstance))}},Je=new _("DialogScrollStrategy",{providedIn:"root",factory:()=>{let i=l(x);return()=>_t(i)}}),Ke=new _("DialogData"),Ze=new _("DefaultDialogConfig");function Ye(i){let a=dt(i),t=new A;return{valueSignal:a,get value(){return a()},change:t,ngOnDestroy(){t.complete()}}}var Bt=(()=>{class i{_injector=l(x);_defaultOptions=l(Ze,{optional:!0});_parentDialog=l(i,{optional:!0,skipSelf:!0});_overlayContainer=l(fe);_idGenerator=l(P);_openDialogsAtThisLevel=[];_afterAllClosedAtThisLevel=new D;_afterOpenedAtThisLevel=new D;_ariaHiddenElements=new Map;_scrollStrategy=l(Je);get openDialogs(){return this._parentDialog?this._parentDialog.openDialogs:this._openDialogsAtThisLevel}get afterOpened(){return this._parentDialog?this._parentDialog.afterOpened:this._afterOpenedAtThisLevel}afterAllClosed=lt(()=>this.openDialogs.length?this._getAfterAllClosed():this._getAfterAllClosed().pipe(ct(void 0)));constructor(){}open(t,e){let n=this._defaultOptions||new B;e=S(S({},n),e),e.id=e.id||this._idGenerator.getId("cdk-dialog-"),e.id&&this.getDialogById(e.id);let o=this._getOverlayConfig(e),r=_e(this._injector,o),s=new rt(r,e),d=this._attachContainer(r,s,e);if(s.containerInstance=d,!this.openDialogs.length){let c=this._overlayContainer.getContainerElement();d._focusTrapped?d._focusTrapped.pipe(z(1)).subscribe(()=>{this._hideNonDialogContentFromAssistiveTechnology(c)}):this._hideNonDialogContentFromAssistiveTechnology(c)}return this._attachDialogContent(t,s,d,e),this.openDialogs.push(s),s.closed.subscribe(()=>this._removeOpenDialog(s,!0)),this.afterOpened.next(s),s}closeAll(){Ft(this.openDialogs,t=>t.close())}getDialogById(t){return this.openDialogs.find(e=>e.id===t)}ngOnDestroy(){Ft(this._openDialogsAtThisLevel,t=>{t.config.closeOnDestroy===!1&&this._removeOpenDialog(t,!1)}),Ft(this._openDialogsAtThisLevel,t=>t.close()),this._afterAllClosedAtThisLevel.complete(),this._afterOpenedAtThisLevel.complete(),this._openDialogsAtThisLevel=[]}_getOverlayConfig(t){let e=new he({positionStrategy:t.positionStrategy||vt().centerHorizontally().centerVertically(),scrollStrategy:t.scrollStrategy||this._scrollStrategy(),panelClass:t.panelClass,hasBackdrop:t.hasBackdrop,direction:t.direction,minWidth:t.minWidth,minHeight:t.minHeight,maxWidth:t.maxWidth,maxHeight:t.maxHeight,width:t.width,height:t.height,disposeOnNavigation:t.closeOnNavigation,disableAnimations:t.disableAnimations});return t.backdropClass&&(e.backdropClass=t.backdropClass),e}_attachContainer(t,e,n){let o=n.injector||n.viewContainerRef?.injector,r=[{provide:B,useValue:n},{provide:rt,useValue:e},{provide:be,useValue:t}],s;n.container?typeof n.container=="function"?s=n.container:(s=n.container.type,r.push(...n.container.providers(n))):s=Pt;let d=new Rt(s,n.viewContainerRef,x.create({parent:o||this._injector,providers:r}));return t.attach(d).instance}_attachDialogContent(t,e,n,o){if(t instanceof Jt){let r=this._createInjector(o,e,n,void 0),s={$implicit:o.data,dialogRef:e};o.templateContext&&(s=S(S({},s),typeof o.templateContext=="function"?o.templateContext():o.templateContext)),n.attachTemplatePortal(new me(t,null,s,r))}else{let r=this._createInjector(o,e,n,this._injector),s=n.attachComponentPortal(new Rt(t,o.viewContainerRef,r));e.componentRef=s,e.componentInstance=s.instance}}_createInjector(t,e,n,o){let r=t.injector||t.viewContainerRef?.injector,s=[{provide:Ke,useValue:t.data},{provide:rt,useValue:e}];return t.providers&&(typeof t.providers=="function"?s.push(...t.providers(e,t,n)):s.push(...t.providers)),t.direction&&(!r||!r.get(et,null,{optional:!0}))&&s.push({provide:et,useValue:Ye(t.direction)}),x.create({parent:r||o,providers:s})}_removeOpenDialog(t,e){let n=this.openDialogs.indexOf(t);n>-1&&(this.openDialogs.splice(n,1),this.openDialogs.length||(this._ariaHiddenElements.forEach((o,r)=>{o?r.setAttribute("aria-hidden",o):r.removeAttribute("aria-hidden")}),this._ariaHiddenElements.clear(),e&&this._getAfterAllClosed().next()))}_hideNonDialogContentFromAssistiveTechnology(t){if(t.parentElement){let e=t.parentElement.children;for(let n=e.length-1;n>-1;n--){let o=e[n];o!==t&&o.nodeName!=="SCRIPT"&&o.nodeName!=="STYLE"&&!o.hasAttribute("aria-live")&&!o.hasAttribute("popover")&&(this._ariaHiddenElements.set(o,o.getAttribute("aria-hidden")),o.setAttribute("aria-hidden","true"))}}}_getAfterAllClosed(){let t=this._parentDialog;return t?t._getAfterAllClosed():this._afterAllClosedAtThisLevel}static \u0275fac=function(e){return new(e||i)};static \u0275prov=w({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})();function Ft(i,a){let t=i.length;for(;t--;)a(i[t])}var Ee=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275mod=E({type:i});static \u0275inj=I({providers:[Bt],imports:[yt,it,ke,it]})}return i})();function Xe(i,a){}var St=class{viewContainerRef;injector;id;role="dialog";panelClass="";hasBackdrop=!0;backdropClass="";disableClose=!1;closePredicate;width="";height="";minWidth;minHeight;maxWidth;maxHeight;position;data=null;direction;ariaDescribedBy=null;ariaLabelledBy=null;ariaLabel=null;ariaModal=!1;autoFocus="first-tabbable";restoreFocus=!0;delayFocusTrap=!0;scrollStrategy;closeOnNavigation=!0;enterAnimationDuration;exitAnimationDuration},Nt="mdc-dialog--open",Me="mdc-dialog--opening",Re="mdc-dialog--closing",tn=150,en=75,nn=(()=>{class i extends Pt{_animationStateChanged=new A;_animationsEnabled=!ot();_actionSectionCount=0;_hostElement=this._elementRef.nativeElement;_enterAnimationDuration=this._animationsEnabled?Pe(this._config.enterAnimationDuration)??tn:0;_exitAnimationDuration=this._animationsEnabled?Pe(this._config.exitAnimationDuration)??en:0;_animationTimer=null;_contentAttached(){super._contentAttached(),this._startOpenAnimation()}_startOpenAnimation(){this._animationStateChanged.emit({state:"opening",totalTime:this._enterAnimationDuration}),this._animationsEnabled?(this._hostElement.style.setProperty(Fe,`${this._enterAnimationDuration}ms`),this._requestAnimationFrame(()=>this._hostElement.classList.add(Me,Nt)),this._waitForAnimationToComplete(this._enterAnimationDuration,this._finishDialogOpen)):(this._hostElement.classList.add(Nt),Promise.resolve().then(()=>this._finishDialogOpen()))}_startExitAnimation(){this._animationStateChanged.emit({state:"closing",totalTime:this._exitAnimationDuration}),this._hostElement.classList.remove(Nt),this._animationsEnabled?(this._hostElement.style.setProperty(Fe,`${this._exitAnimationDuration}ms`),this._requestAnimationFrame(()=>this._hostElement.classList.add(Re)),this._waitForAnimationToComplete(this._exitAnimationDuration,this._finishDialogClose)):Promise.resolve().then(()=>this._finishDialogClose())}_updateActionSectionCount(t){this._actionSectionCount+=t,this._changeDetectorRef.markForCheck()}_finishDialogOpen=()=>{this._clearAnimationClasses(),this._openAnimationDone(this._enterAnimationDuration)};_finishDialogClose=()=>{this._clearAnimationClasses(),this._animationStateChanged.emit({state:"closed",totalTime:this._exitAnimationDuration})};_clearAnimationClasses(){this._hostElement.classList.remove(Me,Re)}_waitForAnimationToComplete(t,e){this._animationTimer!==null&&clearTimeout(this._animationTimer),this._animationTimer=setTimeout(e,t)}_requestAnimationFrame(t){this._ngZone.runOutsideAngular(()=>{typeof requestAnimationFrame=="function"?requestAnimationFrame(t):t()})}_captureInitialFocus(){this._config.delayFocusTrap||this._trapFocus()}_openAnimationDone(t){this._config.delayFocusTrap&&this._trapFocus(),this._animationStateChanged.next({state:"opened",totalTime:t})}ngOnDestroy(){super.ngOnDestroy(),this._animationTimer!==null&&clearTimeout(this._animationTimer)}attachComponentPortal(t){let e=super.attachComponentPortal(t);return e.location.nativeElement.classList.add("mat-mdc-dialog-component-host"),e}static \u0275fac=(()=>{let t;return function(n){return(t||(t=ut(i)))(n||i)}})();static \u0275cmp=O({type:i,selectors:[["mat-dialog-container"]],hostAttrs:["tabindex","-1",1,"mat-mdc-dialog-container","mdc-dialog"],hostVars:10,hostBindings:function(e,n){e&2&&(Et("id",n._config.id),m("aria-modal",n._config.ariaModal)("role",n._config.role)("aria-labelledby",n._config.ariaLabel?null:n._ariaLabelledByQueue[0])("aria-label",n._config.ariaLabel)("aria-describedby",n._config.ariaDescribedBy||null),F("_mat-animation-noopable",!n._animationsEnabled)("mat-mdc-dialog-container-with-actions",n._actionSectionCount>0))},features:[W],decls:3,vars:0,consts:[[1,"mat-mdc-dialog-inner-container","mdc-dialog__container"],[1,"mat-mdc-dialog-surface","mdc-dialog__surface"],["cdkPortalOutlet",""]],template:function(e,n){e&1&&(v(0,"div",0)(1,"div",1),$(2,Xe,0,0,"ng-template",2),C()())},dependencies:[nt],styles:[`.mat-mdc-dialog-container {
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
`],encapsulation:2})}return i})(),Fe="--mat-dialog-transition-duration";function Pe(i){return i==null?null:typeof i=="number"?i:i.endsWith("ms")?Mt(i.substring(0,i.length-2)):i.endsWith("s")?Mt(i.substring(0,i.length-1))*1e3:i==="0"?0:null}var Dt=(function(i){return i[i.OPEN=0]="OPEN",i[i.CLOSING=1]="CLOSING",i[i.CLOSED=2]="CLOSED",i})(Dt||{}),st=class{_ref;_config;_containerInstance;componentInstance;componentRef=null;disableClose;id;_afterOpened=new At(1);_beforeClosed=new At(1);_result;_closeFallbackTimeout;_state=Dt.OPEN;_closeInteractionType;constructor(a,t,e){this._ref=a,this._config=t,this._containerInstance=e,this.disableClose=t.disableClose,this.id=a.id,a.addPanelClass("mat-mdc-dialog-panel"),e._animationStateChanged.pipe(X(n=>n.state==="opened"),z(1)).subscribe(()=>{this._afterOpened.next(),this._afterOpened.complete()}),e._animationStateChanged.pipe(X(n=>n.state==="closed"),z(1)).subscribe(()=>{clearTimeout(this._closeFallbackTimeout),this._finishDialogClose()}),a.overlayRef.detachments().subscribe(()=>{this._beforeClosed.next(this._result),this._beforeClosed.complete(),this._finishDialogClose()}),zt(this.backdropClick(),this.keydownEvents().pipe(X(n=>n.keyCode===27&&!this.disableClose&&!K(n)))).subscribe(n=>{this.disableClose||(n.preventDefault(),Be(this,n.type==="keydown"?"keyboard":"mouse"))})}close(a){let t=this._config.closePredicate;t&&!t(a,this._config,this.componentInstance)||(this._result=a,this._containerInstance._animationStateChanged.pipe(X(e=>e.state==="closing"),z(1)).subscribe(e=>{this._beforeClosed.next(a),this._beforeClosed.complete(),this._ref.overlayRef.detachBackdrop(),this._closeFallbackTimeout=setTimeout(()=>this._finishDialogClose(),e.totalTime+100)}),this._state=Dt.CLOSING,this._containerInstance._startExitAnimation())}afterOpened(){return this._afterOpened}afterClosed(){return this._ref.closed}beforeClosed(){return this._beforeClosed}backdropClick(){return this._ref.backdropClick}keydownEvents(){return this._ref.keydownEvents}updatePosition(a){let t=this._ref.config.positionStrategy;return a&&(a.left||a.right)?a.left?t.left(a.left):t.right(a.right):t.centerHorizontally(),a&&(a.top||a.bottom)?a.top?t.top(a.top):t.bottom(a.bottom):t.centerVertically(),this._ref.updatePosition(),this}updateSize(a="",t=""){return this._ref.updateSize(a,t),this}addPanelClass(a){return this._ref.addPanelClass(a),this}removePanelClass(a){return this._ref.removePanelClass(a),this}getState(){return this._state}_finishDialogClose(){this._state=Dt.CLOSED,this._ref.close(this._result,{focusOrigin:this._closeInteractionType}),this.componentInstance=null}};function Be(i,a,t){return i._closeInteractionType=a,i.close(t)}var on=new _("MatMdcDialogData"),an=new _("mat-mdc-dialog-default-options"),rn=new _("mat-mdc-dialog-scroll-strategy",{providedIn:"root",factory:()=>{let i=l(x);return()=>_t(i)}}),Lt=(()=>{class i{_defaultOptions=l(an,{optional:!0});_scrollStrategy=l(rn);_parentDialog=l(i,{optional:!0,skipSelf:!0});_idGenerator=l(P);_injector=l(x);_dialog=l(Bt);_animationsDisabled=ot();_openDialogsAtThisLevel=[];_afterAllClosedAtThisLevel=new D;_afterOpenedAtThisLevel=new D;dialogConfigClass=St;_dialogRefConstructor;_dialogContainerType;_dialogDataToken;get openDialogs(){return this._parentDialog?this._parentDialog.openDialogs:this._openDialogsAtThisLevel}get afterOpened(){return this._parentDialog?this._parentDialog.afterOpened:this._afterOpenedAtThisLevel}_getAfterAllClosed(){let t=this._parentDialog;return t?t._getAfterAllClosed():this._afterAllClosedAtThisLevel}afterAllClosed=lt(()=>this.openDialogs.length?this._getAfterAllClosed():this._getAfterAllClosed().pipe(ct(void 0)));constructor(){this._dialogRefConstructor=st,this._dialogContainerType=nn,this._dialogDataToken=on}open(t,e){let n;e=S(S({},this._defaultOptions||new St),e),e.id=e.id||this._idGenerator.getId("mat-mdc-dialog-"),e.scrollStrategy=e.scrollStrategy||this._scrollStrategy();let o=this._dialog.open(t,jt(S({},e),{positionStrategy:vt(this._injector).centerHorizontally().centerVertically(),disableClose:!0,closePredicate:void 0,closeOnDestroy:!1,closeOnOverlayDetachments:!1,disableAnimations:this._animationsDisabled||e.enterAnimationDuration?.toLocaleString()==="0"||e.exitAnimationDuration?.toString()==="0",container:{type:this._dialogContainerType,providers:()=>[{provide:this.dialogConfigClass,useValue:e},{provide:B,useValue:e}]},templateContext:()=>({dialogRef:n}),providers:(r,s,d)=>(n=new this._dialogRefConstructor(r,e,d),n.updatePosition(e?.position),[{provide:this._dialogContainerType,useValue:d},{provide:this._dialogDataToken,useValue:s.data},{provide:this._dialogRefConstructor,useValue:n}])}));return n.componentRef=o.componentRef,n.componentInstance=o.componentInstance,this.openDialogs.push(n),this.afterOpened.next(n),n.afterClosed().subscribe(()=>{let r=this.openDialogs.indexOf(n);r>-1&&(this.openDialogs.splice(r,1),this.openDialogs.length||this._getAfterAllClosed().next())}),n}closeAll(){this._closeDialogs(this.openDialogs)}getDialogById(t){return this.openDialogs.find(e=>e.id===t)}ngOnDestroy(){this._closeDialogs(this._openDialogsAtThisLevel),this._afterAllClosedAtThisLevel.complete(),this._afterOpenedAtThisLevel.complete()}_closeDialogs(t){let e=t.length;for(;e--;)t[e].close()}static \u0275fac=function(e){return new(e||i)};static \u0275prov=w({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})(),vi=(()=>{class i{dialogRef=l(st,{optional:!0});_elementRef=l(T);_dialog=l(Lt);ariaLabel;type="button";dialogResult;_matDialogClose;constructor(){}ngOnInit(){this.dialogRef||(this.dialogRef=Le(this._elementRef,this._dialog.openDialogs))}ngOnChanges(t){let e=t._matDialogClose||t._matDialogCloseResult;e&&(this.dialogResult=e.currentValue)}_onButtonClick(t){Be(this.dialogRef,t.screenX===0&&t.screenY===0?"keyboard":"mouse",this.dialogResult)}static \u0275fac=function(e){return new(e||i)};static \u0275dir=M({type:i,selectors:[["","mat-dialog-close",""],["","matDialogClose",""]],hostVars:2,hostBindings:function(e,n){e&1&&Q("click",function(r){return n._onButtonClick(r)}),e&2&&m("aria-label",n.ariaLabel||null)("type",n.type)},inputs:{ariaLabel:[0,"aria-label","ariaLabel"],type:"type",dialogResult:[0,"mat-dialog-close","dialogResult"],_matDialogClose:[0,"matDialogClose","_matDialogClose"]},exportAs:["matDialogClose"],features:[Qt]})}return i})(),Ne=(()=>{class i{_dialogRef=l(st,{optional:!0});_elementRef=l(T);_dialog=l(Lt);constructor(){}ngOnInit(){this._dialogRef||(this._dialogRef=Le(this._elementRef,this._dialog.openDialogs)),this._dialogRef&&Promise.resolve().then(()=>{this._onAdd()})}ngOnDestroy(){this._dialogRef?._containerInstance&&Promise.resolve().then(()=>{this._onRemove()})}static \u0275fac=function(e){return new(e||i)};static \u0275dir=M({type:i})}return i})(),yi=(()=>{class i extends Ne{id=l(P).getId("mat-mdc-dialog-title-");_onAdd(){this._dialogRef._containerInstance?._addAriaLabelledBy?.(this.id)}_onRemove(){this._dialogRef?._containerInstance?._removeAriaLabelledBy?.(this.id)}static \u0275fac=(()=>{let t;return function(n){return(t||(t=ut(i)))(n||i)}})();static \u0275dir=M({type:i,selectors:[["","mat-dialog-title",""],["","matDialogTitle",""]],hostAttrs:[1,"mat-mdc-dialog-title","mdc-dialog__title"],hostVars:1,hostBindings:function(e,n){e&2&&Et("id",n.id)},inputs:{id:"id"},exportAs:["matDialogTitle"],features:[W]})}return i})(),Ci=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275dir=M({type:i,selectors:[["","mat-dialog-content",""],["mat-dialog-content"],["","matDialogContent",""]],hostAttrs:[1,"mat-mdc-dialog-content","mdc-dialog__content"],features:[Zt([ge])]})}return i})(),ki=(()=>{class i extends Ne{align;_onAdd(){this._dialogRef._containerInstance?._updateActionSectionCount?.(1)}_onRemove(){this._dialogRef._containerInstance?._updateActionSectionCount?.(-1)}static \u0275fac=(()=>{let t;return function(n){return(t||(t=ut(i)))(n||i)}})();static \u0275dir=M({type:i,selectors:[["","mat-dialog-actions",""],["mat-dialog-actions"],["","matDialogActions",""]],hostAttrs:[1,"mat-mdc-dialog-actions","mdc-dialog__actions"],hostVars:6,hostBindings:function(e,n){e&2&&F("mat-mdc-dialog-actions-align-start",n.align==="start")("mat-mdc-dialog-actions-align-center",n.align==="center")("mat-mdc-dialog-actions-align-end",n.align==="end")},inputs:{align:"align"},features:[W]})}return i})();function Le(i,a){let t=i.nativeElement.parentElement;for(;t&&!t.classList.contains("mat-mdc-dialog-container");)t=t.parentElement;return t?a.find(e=>e.id===t.id):null}var Di=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275mod=E({type:i});static \u0275inj=I({providers:[Lt],imports:[Ee,yt,it,J]})}return i})();var mn=["button"],pn=["*"];function hn(i,a){if(i&1&&(v(0,"div",2),U(1,"mat-pseudo-checkbox",6),C()),i&2){let t=mt();y(),R("disabled",t.disabled)}}var je=new _("MAT_BUTTON_TOGGLE_DEFAULT_OPTIONS",{providedIn:"root",factory:()=>({hideSingleSelectionIndicator:!1,hideMultipleSelectionIndicator:!1,disabledInteractive:!1})}),Ge=new _("MatButtonToggleGroup"),fn={provide:ve,useExisting:Ht(()=>bn),multi:!0},xt=class{source;value;constructor(a,t){this.source=a,this.value=t}},bn=(()=>{class i{_changeDetector=l(tt);_dir=l(et,{optional:!0});_multiple=!1;_disabled=!1;_disabledInteractive=!1;_selectionModel;_rawValue;_controlValueAccessorChangeFn=()=>{};_onTouched=()=>{};_buttonToggles;appearance;get name(){return this._name}set name(t){this._name=t,this._markButtonsForCheck()}_name=l(P).getId("mat-button-toggle-group-");vertical=!1;get value(){let t=this._selectionModel?this._selectionModel.selected:[];return this.multiple?t.map(e=>e.value):t[0]?t[0].value:void 0}set value(t){this._setSelectionByValue(t),this.valueChange.emit(this.value)}valueChange=new A;get selected(){let t=this._selectionModel?this._selectionModel.selected:[];return this.multiple?t:t[0]||null}get multiple(){return this._multiple}set multiple(t){this._multiple=t,this._markButtonsForCheck()}get disabled(){return this._disabled}set disabled(t){this._disabled=t,this._markButtonsForCheck()}get disabledInteractive(){return this._disabledInteractive}set disabledInteractive(t){this._disabledInteractive=t,this._markButtonsForCheck()}get dir(){return this._dir&&this._dir.value==="rtl"?"rtl":"ltr"}change=new A;get hideSingleSelectionIndicator(){return this._hideSingleSelectionIndicator}set hideSingleSelectionIndicator(t){this._hideSingleSelectionIndicator=t,this._markButtonsForCheck()}_hideSingleSelectionIndicator;get hideMultipleSelectionIndicator(){return this._hideMultipleSelectionIndicator}set hideMultipleSelectionIndicator(t){this._hideMultipleSelectionIndicator=t,this._markButtonsForCheck()}_hideMultipleSelectionIndicator;constructor(){let t=l(je,{optional:!0});this.appearance=t&&t.appearance?t.appearance:"standard",this._hideSingleSelectionIndicator=t?.hideSingleSelectionIndicator??!1,this._hideMultipleSelectionIndicator=t?.hideMultipleSelectionIndicator??!1}ngOnInit(){this._selectionModel=new we(this.multiple,void 0,!1)}ngAfterContentInit(){this._selectionModel.select(...this._buttonToggles.filter(t=>t.checked)),this.multiple||this._initializeTabIndex()}writeValue(t){this.value=t,this._changeDetector.markForCheck()}registerOnChange(t){this._controlValueAccessorChangeFn=t}registerOnTouched(t){this._onTouched=t}setDisabledState(t){this.disabled=t}_keydown(t){if(this.multiple||this.disabled||K(t))return;let n=t.target.id,o=this._buttonToggles.toArray().findIndex(s=>s.buttonId===n),r=null;switch(t.keyCode){case 32:case 13:r=this._buttonToggles.get(o)||null;break;case 38:r=this._getNextButton(o,-1);break;case 37:r=this._getNextButton(o,this.dir==="ltr"?-1:1);break;case 40:r=this._getNextButton(o,1);break;case 39:r=this._getNextButton(o,this.dir==="ltr"?1:-1);break;default:return}r&&(t.preventDefault(),r._onButtonClick(),r.focus())}_emitChangeEvent(t){let e=new xt(t,this.value);this._rawValue=e.value,this._controlValueAccessorChangeFn(e.value),this.change.emit(e)}_syncButtonToggle(t,e,n=!1,o=!1){!this.multiple&&this.selected&&!t.checked&&(this.selected.checked=!1),this._selectionModel?e?this._selectionModel.select(t):this._selectionModel.deselect(t):o=!0,o?Promise.resolve().then(()=>this._updateModelValue(t,n)):this._updateModelValue(t,n)}_isSelected(t){return this._selectionModel&&this._selectionModel.isSelected(t)}_isPrechecked(t){return typeof this._rawValue>"u"?!1:this.multiple&&Array.isArray(this._rawValue)?this._rawValue.some(e=>t.value!=null&&e===t.value):t.value===this._rawValue}_initializeTabIndex(){if(this._buttonToggles.forEach(t=>{t.tabIndex=-1}),this.selected)this.selected.tabIndex=0;else for(let t=0;t<this._buttonToggles.length;t++){let e=this._buttonToggles.get(t);if(!e.disabled){e.tabIndex=0;break}}}_getNextButton(t,e){let n=this._buttonToggles;for(let o=1;o<=n.length;o++){let r=(t+e*o+n.length)%n.length,s=n.get(r);if(s&&!s.disabled)return s}return null}_setSelectionByValue(t){if(this._rawValue=t,!this._buttonToggles)return;let e=this._buttonToggles.toArray();if(this.multiple&&t?(Array.isArray(t),this._clearSelection(),t.forEach(n=>this._selectValue(n,e))):(this._clearSelection(),this._selectValue(t,e)),!this.multiple&&e.every(n=>n.tabIndex===-1)){for(let n of e)if(!n.disabled){n.tabIndex=0;break}}}_clearSelection(){this._selectionModel.clear(),this._buttonToggles.forEach(t=>{t.checked=!1,this.multiple||(t.tabIndex=-1)})}_selectValue(t,e){for(let n of e)if(n.value===t){n.checked=!0,this._selectionModel.select(n),this.multiple||(n.tabIndex=0);break}}_updateModelValue(t,e){e&&this._emitChangeEvent(t),this.valueChange.emit(this.value)}_markButtonsForCheck(){this._buttonToggles?.forEach(t=>t._markForCheck())}static \u0275fac=function(e){return new(e||i)};static \u0275dir=M({type:i,selectors:[["mat-button-toggle-group"]],contentQueries:function(e,n,o){if(e&1&&ne(o,Ve,5),e&2){let r;G(r=V())&&(n._buttonToggles=r)}},hostAttrs:[1,"mat-button-toggle-group"],hostVars:6,hostBindings:function(e,n){e&1&&Q("keydown",function(r){return n._keydown(r)}),e&2&&(m("role",n.multiple?"group":"radiogroup")("aria-disabled",n.disabled),F("mat-button-toggle-vertical",n.vertical)("mat-button-toggle-group-appearance-standard",n.appearance==="standard"))},inputs:{appearance:"appearance",name:"name",vertical:[2,"vertical","vertical",k],value:"value",multiple:[2,"multiple","multiple",k],disabled:[2,"disabled","disabled",k],disabledInteractive:[2,"disabledInteractive","disabledInteractive",k],hideSingleSelectionIndicator:[2,"hideSingleSelectionIndicator","hideSingleSelectionIndicator",k],hideMultipleSelectionIndicator:[2,"hideMultipleSelectionIndicator","hideMultipleSelectionIndicator",k]},outputs:{valueChange:"valueChange",change:"change"},exportAs:["matButtonToggleGroup"],features:[oe([fn,{provide:Ge,useExisting:i}])]})}return i})(),Ve=(()=>{class i{_changeDetectorRef=l(tt);_elementRef=l(T);_focusMonitor=l(Ct);_idGenerator=l(P);_animationDisabled=ot();_checked=!1;ariaLabel;ariaLabelledby=null;_buttonElement;buttonToggleGroup;get buttonId(){return`${this.id}-button`}id;name;value;get tabIndex(){return this._tabIndex()}set tabIndex(t){this._tabIndex.set(t)}_tabIndex;disableRipple=!1;get appearance(){return this.buttonToggleGroup?this.buttonToggleGroup.appearance:this._appearance}set appearance(t){this._appearance=t}_appearance;get checked(){return this.buttonToggleGroup?this.buttonToggleGroup._isSelected(this):this._checked}set checked(t){t!==this._checked&&(this._checked=t,this.buttonToggleGroup&&this.buttonToggleGroup._syncButtonToggle(this,this._checked),this._changeDetectorRef.markForCheck())}get disabled(){return this._disabled||this.buttonToggleGroup&&this.buttonToggleGroup.disabled}set disabled(t){this._disabled=t}_disabled=!1;get disabledInteractive(){return this._disabledInteractive||this.buttonToggleGroup!==null&&this.buttonToggleGroup.disabledInteractive}set disabledInteractive(t){this._disabledInteractive=t}_disabledInteractive;change=new A;constructor(){l(de).load(xe);let t=l(Ge,{optional:!0}),e=l(new re("tabindex"),{optional:!0})||"",n=l(je,{optional:!0});this._tabIndex=dt(parseInt(e)||0),this.buttonToggleGroup=t,this._appearance=n&&n.appearance?n.appearance:"standard",this._disabledInteractive=n?.disabledInteractive??!1}ngOnInit(){let t=this.buttonToggleGroup;this.id=this.id||this._idGenerator.getId("mat-button-toggle-"),t&&(t._isPrechecked(this)?this.checked=!0:t._isSelected(this)!==this._checked&&t._syncButtonToggle(this,this._checked))}ngAfterViewInit(){this._animationDisabled||this._elementRef.nativeElement.classList.add("mat-button-toggle-animations-enabled"),this._focusMonitor.monitor(this._elementRef,!0)}ngOnDestroy(){let t=this.buttonToggleGroup;this._focusMonitor.stopMonitoring(this._elementRef),t&&t._isSelected(this)&&t._syncButtonToggle(this,!1,!1,!0)}focus(t){this._buttonElement.nativeElement.focus(t)}_onButtonClick(){if(this.disabled)return;let t=this.isSingleSelector()?!0:!this._checked;if(t!==this._checked&&(this._checked=t,this.buttonToggleGroup&&(this.buttonToggleGroup._syncButtonToggle(this,this._checked,!0),this.buttonToggleGroup._onTouched())),this.isSingleSelector()){let e=this.buttonToggleGroup._buttonToggles.find(n=>n.tabIndex===0);e&&(e.tabIndex=-1),this.tabIndex=0}this.change.emit(new xt(this,this.value))}_markForCheck(){this._changeDetectorRef.markForCheck()}_getButtonName(){return this.isSingleSelector()?this.buttonToggleGroup.name:this.name||null}isSingleSelector(){return this.buttonToggleGroup&&!this.buttonToggleGroup.multiple}static \u0275fac=function(e){return new(e||i)};static \u0275cmp=O({type:i,selectors:[["mat-button-toggle"]],viewQuery:function(e,n){if(e&1&&q(mn,5),e&2){let o;G(o=V())&&(n._buttonElement=o.first)}},hostAttrs:["role","presentation",1,"mat-button-toggle"],hostVars:14,hostBindings:function(e,n){e&1&&Q("focus",function(){return n.focus()}),e&2&&(m("aria-label",null)("aria-labelledby",null)("id",n.id)("name",null),F("mat-button-toggle-standalone",!n.buttonToggleGroup)("mat-button-toggle-checked",n.checked)("mat-button-toggle-disabled",n.disabled)("mat-button-toggle-disabled-interactive",n.disabledInteractive)("mat-button-toggle-appearance-standard",n.appearance==="standard"))},inputs:{ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"],id:"id",name:"name",value:"value",tabIndex:"tabIndex",disableRipple:[2,"disableRipple","disableRipple",k],appearance:"appearance",checked:[2,"checked","checked",k],disabled:[2,"disabled","disabled",k],disabledInteractive:[2,"disabledInteractive","disabledInteractive",k]},outputs:{change:"change"},exportAs:["matButtonToggle"],ngContentSelectors:pn,decls:7,vars:13,consts:[["button",""],["type","button",1,"mat-button-toggle-button","mat-focus-indicator",3,"click","id","disabled"],[1,"mat-button-toggle-checkbox-wrapper"],[1,"mat-button-toggle-label-content"],[1,"mat-button-toggle-focus-overlay"],["matRipple","",1,"mat-button-toggle-ripple",3,"matRippleTrigger","matRippleDisabled"],["state","checked","aria-hidden","true","appearance","minimal",3,"disabled"]],template:function(e,n){if(e&1&&(te(),v(0,"button",1,0),Q("click",function(){return n._onButtonClick()}),Yt(2,hn,2,1,"div",2),v(3,"span",3),ee(4),C()(),U(5,"span",4)(6,"span",5)),e&2){let o=pt(1);R("id",n.buttonId)("disabled",n.disabled&&!n.disabledInteractive||null),m("role",n.isSingleSelector()?"radio":"button")("tabindex",n.disabled&&!n.disabledInteractive?-1:n.tabIndex)("aria-pressed",n.isSingleSelector()?null:n.checked)("aria-checked",n.isSingleSelector()?n.checked:null)("name",n._getButtonName())("aria-label",n.ariaLabel)("aria-labelledby",n.ariaLabelledby)("aria-disabled",n.disabled&&n.disabledInteractive?"true":null),y(2),Xt(n.buttonToggleGroup&&(!n.buttonToggleGroup.multiple&&!n.buttonToggleGroup.hideSingleSelectionIndicator||n.buttonToggleGroup.multiple&&!n.buttonToggleGroup.hideMultipleSelectionIndicator)?2:-1),y(4),R("matRippleTrigger",o)("matRippleDisabled",n.disableRipple||n.disabled)}},dependencies:[Se,Ie],styles:[`.mat-button-toggle-standalone,
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
`],encapsulation:2,changeDetection:0})}return i})(),Qi=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275mod=E({type:i});static \u0275inj=I({imports:[Te,Ve,J]})}return i})();function _n(i){return i.metadata&&(typeof i.metadata=="string"?JSON.parse(i.metadata):i.metadata).copilot_mode||null}function Ji(i){return _n(i)==="troubleshooting_injection"}var Z=(function(i){return i.NETWORK_ERROR="NETWORK_ERROR",i.PROJECT_NOT_OPENED="PROJECT_NOT_OPENED",i.LLM_NOT_CONFIGURED="LLM_NOT_CONFIGURED",i.SESSION_NOT_FOUND="SESSION_NOT_FOUND",i.UNAUTHORIZED="UNAUTHORIZED",i.UNKNOWN_ERROR="UNKNOWN_ERROR",i})(Z||{});var Tt=class{authToken;id;name;location;host;port;path;ubridge_path;status="stopped";protocol;username;password;tokenExpired=!1};var ze=(()=>{class i{httpController;controllerIds=[];serviceInitialized=new D;isServiceInitialized;constructor(t){this.httpController=t,this.controllerIds=this.getcontrollerIds(),this.isServiceInitialized=!0,this.serviceInitialized.next(this.isServiceInitialized)}getcontrollerIds(){let t=localStorage.getItem("controllerIds");if(t?.length>0){let e=t.split(",");return[...new Set(e)].filter(n=>n&&n.trim().length>0)}return[]}updatecontrollerIds(){localStorage.removeItem("controllerIds"),localStorage.setItem("controllerIds",this.controllerIds.toString())}get(t){let e=JSON.parse(localStorage.getItem(`controller-${t}`));return new Promise(o=>{o(e)})}create(t){if(this.findAllSync().some(s=>s.name===t.name))return Promise.reject(new Error(`Controller with name "${t.name}" already exists`));let n=this.controllerIds.map(s=>parseInt(s.replace("controller-",""),10)).filter(s=>!isNaN(s)),o=n.length>0?Math.max(...n):0;return t.id=o+1,localStorage.setItem(`controller-${t.id}`,JSON.stringify(t)),this.controllerIds.push(`controller-${t.id}`),this.updatecontrollerIds(),new Promise(s=>{s(t)})}findAllSync(){let t=[];return this.controllerIds.forEach(e=>{let n=localStorage.getItem(e);n&&t.push(JSON.parse(n))}),t}isControllerNameTaken(t){return this.findAllSync().some(n=>n.name===t)}update(t){return localStorage.removeItem(`controller-${t.id}`),localStorage.setItem(`controller-${t.id}`,JSON.stringify(t)),new Promise(n=>{n(t)})}findAll(){return new Promise(e=>{let n=[];this.controllerIds.forEach(o=>{let r=localStorage.getItem(o);if(r){let s=JSON.parse(r);n.push(s)}}),e(n)})}delete(t){return localStorage.removeItem(`controller-${t.id}`),this.controllerIds=this.controllerIds.filter(n=>n!==`controller-${t.id}`),this.updatecontrollerIds(),new Promise(n=>{n(t.id)})}getControllerUrl(t){return`${t.protocol}//${t.host}:${t.port}/`}checkControllerVersion(t){return this.httpController.get(t,"/version").pipe(Vt(5e3),b(e=>{if(e.name==="TimeoutError"){let n=new Error("Connection timeout");return p(()=>n)}return p(()=>e)}))}getLocalController(t,e){return new Promise((o,r)=>{this.findAll().then(s=>{let d=s.find(c=>c.location==="bundled");if(d)d.host=t,d.port=e,d.protocol=location.protocol,this.update(d).then(c=>{o(c)},r);else{let c=new Tt;c.name="local",c.host=t,c.port=e,c.location="bundled",c.protocol=location.protocol,this.create(c).then(N=>{o(N)},r)}},r)})}static \u0275fac=function(e){return new(e||i)(H(kt))};static \u0275prov=w({token:i,factory:i.\u0275fac})}return i})();var ro=(()=>{class i{http;httpController;controllerService;currentProjectId=null;currentSessionId=null;isStreaming=new Gt(!1);constructor(t,e,n){this.http=t,this.httpController=e,this.controllerService=n}injectFault(t,e,n){let o=`${this.getControllerUrl(t)}/v3/copilot/projects/${e}/chat/inject`,r=this.getAuthHeaders(t),s={"Content-Type":"application/json"};return r.keys().forEach(d=>{let c=r.get(d);c&&(s[d]=c)}),new It(d=>(fetch(o,{method:"POST",headers:s,body:JSON.stringify({message:n})}).then(async c=>{if(!c.ok){let u=`HTTP error! status: ${c.status}`;try{let f=await c.json();f.message&&(u=f.message)}catch{c.statusText&&(u=c.statusText)}let h=new Error(u);throw h.status=c.status,h.statusText=c.statusText,h.error={message:u},h}if(!c.body)throw new Error("Response body is null");let N=c.body.getReader(),wt=new TextDecoder,L="";(async()=>{try{for(;;){let{done:u,value:h}=await N.read();if(u){d.complete();break}L+=wt.decode(h,{stream:!0});let f=L.split(`
`);L=f.pop()||"";for(let Y of f)if(Y.startsWith("data: ")){let j=Y.slice(6).trim();if(j)try{let g=JSON.parse(j);if(g.type==="heartbeat")continue;if(d.next(g),g.type==="done"||g.type==="error"){d.complete();break}}catch(g){console.error("Failed to parse SSE data:",j,g)}}if(d.closed)break}}catch(u){console.error("Stream processing error:",u),d.error(u)}finally{N.cancel()}})()}).catch(c=>{console.error("Fetch error:",c),d.error(c)}),()=>{})).pipe(b(d=>p(()=>d)))}streamChat(t,e,n){this.currentProjectId=e,this.isStreaming.next(!0);let o=`${this.getControllerUrl(t)}/v3/copilot/projects/${e}/chat/stream`,r=this.getAuthHeaders(t),s={"Content-Type":"application/json"};return r.keys().forEach(d=>{let c=r.get(d);c&&(s[d]=c)}),new It(d=>(fetch(o,{method:"POST",headers:s,body:JSON.stringify(n)}).then(async c=>{if(!c.ok){let u=`HTTP error! status: ${c.status}`;try{let f=await c.json();f.message&&(u=f.message)}catch{c.statusText&&(u=c.statusText)}let h=new Error(u);throw h.status=c.status,h.statusText=c.statusText,h.error={message:u},h}if(!c.body)throw new Error("Response body is null");let N=c.body.getReader(),wt=new TextDecoder,L="";(async()=>{try{for(;;){let{done:u,value:h}=await N.read();if(u){d.complete();break}L+=wt.decode(h,{stream:!0});let f=L.split(`
`);L=f.pop()||"";for(let Y of f)if(Y.startsWith("data: ")){let j=Y.slice(6).trim();if(j)try{let g=JSON.parse(j);if(g.type==="heartbeat")continue;if(g.session_id&&(this.currentSessionId=g.session_id),d.next(g),g.type==="done"||g.type==="error"){d.complete();break}}catch(g){console.error("Failed to parse SSE data:",j,g)}}if(d.closed)break}}catch(u){console.error("Stream processing error:",u),d.error(u)}finally{N.cancel()}})()}).catch(c=>{console.error("Fetch error:",c),d.error(c)}).finally(()=>{this.isStreaming.next(!1)}),()=>{this.isStreaming.next(!1)})).pipe(b(d=>(this.isStreaming.next(!1),p(()=>d))))}getSessions(t,e){return this.httpController.get(t,`/copilot/projects/${e}/chat/sessions`).pipe(b(n=>(console.error("Failed to get sessions:",n),p(()=>n))))}getSessionHistory(t,e,n,o=100){let r=o?{limit:o}:void 0;return this.httpController.get(t,`/copilot/projects/${e}/chat/sessions/${n}/history`).pipe(b(s=>(console.error("Failed to get session history:",s),p(()=>s))))}renameSession(t,e,n,o){let r={title:o};return this.httpController.patch(t,`/copilot/projects/${e}/chat/sessions/${n}`,r).pipe(b(s=>(console.error("Failed to rename session:",s),p(()=>s))))}deleteSession(t,e,n){return this.httpController.delete(t,`/copilot/projects/${e}/chat/sessions/${n}`).pipe(b(o=>(console.error("Failed to delete session:",o),p(()=>o))))}pinSession(t,e,n){return this.httpController.put(t,`/copilot/projects/${e}/chat/sessions/${n}/pin`,null).pipe(b(o=>(console.error("Failed to pin session:",o),p(()=>o))))}unpinSession(t,e,n){return this.httpController.delete(t,`/copilot/projects/${e}/chat/sessions/${n}/pin`).pipe(b(o=>(console.error("Failed to unpin session:",o),p(()=>o))))}getStreamingState(){return this.isStreaming.asObservable()}abortChat(t,e,n){return this.httpController.post(t,`/copilot/projects/${e}/chat/sessions/${n}/abort`,null).pipe(b(o=>(console.error("Failed to abort chat:",o),p(()=>o))))}getCurrentSessionId(){return this.currentSessionId}resetCurrentSession(){this.currentSessionId=null,this.currentProjectId=null}reloadSkills(t){return this.httpController.post(t,"/copilot/reload/skills",null).pipe(b(e=>(console.error("Failed to reload skills:",e),p(()=>e))))}getControllerUrl(t){return`${t.protocol==="https:"?"https":"http"}://${t.host}:${t.port}`}getAuthHeaders(t){let e=new le;if(t.authToken)return e.set("Authorization",`Bearer ${t.authToken}`);if(t.username&&t.password){let n=btoa(`${t.username}:${t.password}`);return e.set("Authorization",`Basic ${n}`)}return e}createChatError(t){return t.status===401?{type:Z.UNAUTHORIZED,message:"Unauthorized access",details:t}:t.status===404?{type:Z.SESSION_NOT_FOUND,message:"Session not found",details:t}:t.message&&t.message.includes("fetch")?{type:Z.NETWORK_ERROR,message:"Network connection failed",details:t}:{type:Z.UNKNOWN_ERROR,message:t.message||"Unknown error",details:t}}static \u0275fac=function(e){return new(e||i)(H(ce),H(kt),H(ze))};static \u0275prov=w({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})();export{En as a,Mn as b,Tt as c,ze as d,st as e,on as f,Lt as g,vi as h,yi as i,Ci as j,ki as k,Di as l,bn as m,Ve as n,Qi as o,Ji as p,ro as q};
