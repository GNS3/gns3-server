import{A as rt,Ab as N,Ad as ge,Af as Te,Bb as j,Bd as me,Bf as xe,Cd as pe,Cf as Se,Ed as _t,Ef as we,F as jt,Fb as mt,G as Y,Gb as pt,Gd as he,Ha as y,Hb as R,He as ye,I as v,Ia as Ut,Ib as te,Ie as it,Ja as $t,Jc as oe,Jd as vt,La as Qt,Ld as fe,N as G,Oc as re,Pa as I,Qa as O,Ra as E,Ta as qt,Tc as se,Ua as H,Va as z,Vb as ee,Vc as ft,X as st,Ye as Ce,Zc as Ot,_a as m,_e as ke,a as D,ab as Kt,ad as le,af as De,b as Lt,ba as Gt,bd as tt,ca as V,cb as Zt,da as w,dc as ne,ea as f,fa as lt,ga as s,h as St,hb as M,hc as ie,hd as Q,i as S,ib as b,j as Nt,jb as C,jd as ce,k as wt,kb as W,ma as At,me as yt,na as Vt,oa as T,od as F,pa as Ht,pc as X,qb as ut,qd as Et,ra as A,rc as k,rd as de,s as _,sa as zt,sb as It,sc as ht,sd as ue,tb as U,te as be,ua as ct,ue as _e,vb as gt,vd as et,wa as Wt,wb as Jt,wd as nt,we as ve,xa as dt,xb as Yt,xd as q,ya as x,yb as Xt,yd as bt,zb as $,zc as ae}from"./chunk-U3DF4UXB.js";var He=["determinateSpinner"];function ze(i,o){if(i&1&&(At(),b(0,"svg",11),W(1,"circle",12),C()),i&2){let t=gt();m("viewBox",t._viewBox()),y(),pt("stroke-dasharray",t._strokeCircumference(),"px")("stroke-dashoffset",t._strokeCircumference()/2,"px")("stroke-width",t._circleStrokeWidth(),"%"),m("r",t._circleRadius())}}var We=new f("mat-progress-spinner-default-options",{providedIn:"root",factory:()=>({diameter:Ae})}),Ae=100,Ue=10,wn=(()=>{class i{_elementRef=s(x);_noopAnimations;get color(){return this._color||this._defaultColor}set color(t){this._color=t}_color;_defaultColor="primary";_determinateCircle;constructor(){let t=s(We),e=ye(),n=this._elementRef.nativeElement;this._noopAnimations=e==="di-disabled"&&!!t&&!t._forceAnimations,this.mode=n.nodeName.toLowerCase()==="mat-spinner"?"indeterminate":"determinate",!this._noopAnimations&&e==="reduced-motion"&&n.classList.add("mat-progress-spinner-reduced-motion"),t&&(t.color&&(this.color=this._defaultColor=t.color),t.diameter&&(this.diameter=t.diameter),t.strokeWidth&&(this.strokeWidth=t.strokeWidth))}mode;get value(){return this.mode==="determinate"?this._value:0}set value(t){this._value=Math.max(0,Math.min(100,t||0))}_value=0;get diameter(){return this._diameter}set diameter(t){this._diameter=t||0}_diameter=Ae;get strokeWidth(){return this._strokeWidth??this.diameter/10}set strokeWidth(t){this._strokeWidth=t||0}_strokeWidth;_circleRadius(){return(this.diameter-Ue)/2}_viewBox(){let t=this._circleRadius()*2+this.strokeWidth;return`0 0 ${t} ${t}`}_strokeCircumference(){return 2*Math.PI*this._circleRadius()}_strokeDashOffset(){return this.mode==="determinate"?this._strokeCircumference()*(100-this._value)/100:null}_circleStrokeWidth(){return this.strokeWidth/this.diameter*100}static \u0275fac=function(e){return new(e||i)};static \u0275cmp=I({type:i,selectors:[["mat-progress-spinner"],["mat-spinner"]],viewQuery:function(e,n){if(e&1&&$(He,5),e&2){let a;N(a=j())&&(n._determinateCircle=a.first)}},hostAttrs:["role","progressbar","tabindex","-1",1,"mat-mdc-progress-spinner","mdc-circular-progress"],hostVars:18,hostBindings:function(e,n){e&2&&(m("aria-valuemin",0)("aria-valuemax",100)("aria-valuenow",n.mode==="determinate"?n.value:null)("mode",n.mode),te("mat-"+n.color),pt("width",n.diameter,"px")("height",n.diameter,"px")("--mat-progress-spinner-size",n.diameter+"px")("--mat-progress-spinner-active-indicator-width",n.diameter+"px"),R("_mat-animation-noopable",n._noopAnimations)("mdc-circular-progress--indeterminate",n.mode==="indeterminate"))},inputs:{color:"color",mode:"mode",value:[2,"value","value",ht],diameter:[2,"diameter","diameter",ht],strokeWidth:[2,"strokeWidth","strokeWidth",ht]},exportAs:["matProgressSpinner"],decls:14,vars:11,consts:[["circle",""],["determinateSpinner",""],["aria-hidden","true",1,"mdc-circular-progress__determinate-container"],["xmlns","http://www.w3.org/2000/svg","focusable","false",1,"mdc-circular-progress__determinate-circle-graphic"],["cx","50%","cy","50%",1,"mdc-circular-progress__determinate-circle"],["aria-hidden","true",1,"mdc-circular-progress__indeterminate-container"],[1,"mdc-circular-progress__spinner-layer"],[1,"mdc-circular-progress__circle-clipper","mdc-circular-progress__circle-left"],[3,"ngTemplateOutlet"],[1,"mdc-circular-progress__gap-patch"],[1,"mdc-circular-progress__circle-clipper","mdc-circular-progress__circle-right"],["xmlns","http://www.w3.org/2000/svg","focusable","false",1,"mdc-circular-progress__indeterminate-circle-graphic"],["cx","50%","cy","50%"]],template:function(e,n){if(e&1&&(z(0,ze,2,8,"ng-template",null,0,ne),b(2,"div",2,1),At(),b(4,"svg",3),W(5,"circle",4),C()(),Vt(),b(6,"div",5)(7,"div",6)(8,"div",7),ut(9,8),C(),b(10,"div",9),ut(11,8),C(),b(12,"div",10),ut(13,8),C()()()),e&2){let a=mt(1);y(4),m("viewBox",n._viewBox()),y(),pt("stroke-dasharray",n._strokeCircumference(),"px")("stroke-dashoffset",n._strokeDashOffset(),"px")("stroke-width",n._circleStrokeWidth(),"%"),m("r",n._circleRadius()),y(4),M("ngTemplateOutlet",a),y(2),M("ngTemplateOutlet",a),y(2),M("ngTemplateOutlet",a)}},dependencies:[ae],styles:[`.mat-mdc-progress-spinner {
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
`],encapsulation:2,changeDetection:0})}return i})();var An=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275mod=O({type:i});static \u0275inj=w({imports:[Q]})}return i})();function $e(i,o){}var B=class{viewContainerRef;injector;id;role="dialog";panelClass="";hasBackdrop=!0;backdropClass="";disableClose=!1;closePredicate;width="";height="";minWidth;minHeight;maxWidth;maxHeight;positionStrategy;data=null;direction;ariaDescribedBy=null;ariaLabelledBy=null;ariaLabel=null;ariaModal=!1;autoFocus="first-tabbable";restoreFocus=!0;scrollStrategy;closeOnNavigation=!0;closeOnDestroy=!0;closeOnOverlayDetachments=!0;disableAnimations=!1;providers;container;templateContext};var Rt=(()=>{class i extends ue{_elementRef=s(x);_focusTrapFactory=s(_e);_config;_interactivityChecker=s(be);_ngZone=s(zt);_focusMonitor=s(yt);_renderer=s(Qt);_changeDetectorRef=s(X);_injector=s(T);_platform=s(le);_document=s(Ht);_portalOutlet;_focusTrapped=new S;_focusTrap=null;_elementFocusedBeforeDialogWasOpened=null;_closeInteractionType=null;_ariaLabelledByQueue=[];_isDestroyed=!1;constructor(){super(),this._config=s(B,{optional:!0})||new B,this._config.ariaLabelledBy&&this._ariaLabelledByQueue.push(this._config.ariaLabelledBy)}_addAriaLabelledBy(t){this._ariaLabelledByQueue.push(t),this._changeDetectorRef.markForCheck()}_removeAriaLabelledBy(t){let e=this._ariaLabelledByQueue.indexOf(t);e>-1&&(this._ariaLabelledByQueue.splice(e,1),this._changeDetectorRef.markForCheck())}_contentAttached(){this._initializeFocusTrap(),this._captureInitialFocus()}_captureInitialFocus(){this._trapFocus()}ngOnDestroy(){this._focusTrapped.complete(),this._isDestroyed=!0,this._restoreFocus()}attachComponentPortal(t){this._portalOutlet.hasAttached();let e=this._portalOutlet.attachComponentPortal(t);return this._contentAttached(),e}attachTemplatePortal(t){this._portalOutlet.hasAttached();let e=this._portalOutlet.attachTemplatePortal(t);return this._contentAttached(),e}attachDomPortal=t=>{this._portalOutlet.hasAttached();let e=this._portalOutlet.attachDomPortal(t);return this._contentAttached(),e};_recaptureFocus(){this._containsFocus()||this._trapFocus()}_forceFocus(t,e){this._interactivityChecker.isFocusable(t)||(t.tabIndex=-1,this._ngZone.runOutsideAngular(()=>{let n=()=>{a(),r(),t.removeAttribute("tabindex")},a=this._renderer.listen(t,"blur",n),r=this._renderer.listen(t,"mousedown",n)})),t.focus(e)}_focusByCssSelector(t,e){let n=this._elementRef.nativeElement.querySelector(t);n&&this._forceFocus(n,e)}_trapFocus(t){this._isDestroyed||Ut(()=>{let e=this._elementRef.nativeElement;switch(this._config.autoFocus){case!1:case"dialog":this._containsFocus()||e.focus(t);break;case!0:case"first-tabbable":this._focusTrap?.focusInitialElement(t)||this._focusDialogContainer(t);break;case"first-heading":this._focusByCssSelector('h1, h2, h3, h4, h5, h6, [role="heading"]',t);break;default:this._focusByCssSelector(this._config.autoFocus,t);break}this._focusTrapped.next()},{injector:this._injector})}_restoreFocus(){let t=this._config.restoreFocus,e=null;if(typeof t=="string"?e=this._document.querySelector(t):typeof t=="boolean"?e=t?this._elementFocusedBeforeDialogWasOpened:null:t&&(e=t),this._config.restoreFocus&&e&&typeof e.focus=="function"){let n=ft(),a=this._elementRef.nativeElement;(!n||n===this._document.body||n===a||a.contains(n))&&(this._focusMonitor?(this._focusMonitor.focusVia(e,this._closeInteractionType),this._closeInteractionType=null):e.focus())}this._focusTrap&&this._focusTrap.destroy()}_focusDialogContainer(t){this._elementRef.nativeElement.focus?.(t)}_containsFocus(){let t=this._elementRef.nativeElement,e=ft();return t===e||t.contains(e)}_initializeFocusTrap(){this._platform.isBrowser&&(this._focusTrap=this._focusTrapFactory.create(this._elementRef.nativeElement),this._document&&(this._elementFocusedBeforeDialogWasOpened=ft()))}static \u0275fac=function(e){return new(e||i)};static \u0275cmp=I({type:i,selectors:[["cdk-dialog-container"]],viewQuery:function(e,n){if(e&1&&$(et,7),e&2){let a;N(a=j())&&(n._portalOutlet=a.first)}},hostAttrs:["tabindex","-1",1,"cdk-dialog-container"],hostVars:6,hostBindings:function(e,n){e&2&&m("id",n._config.id||null)("role",n._config.role)("aria-modal",n._config.ariaModal)("aria-labelledby",n._config.ariaLabel?null:n._ariaLabelledByQueue[0])("aria-label",n._config.ariaLabel)("aria-describedby",n._config.ariaDescribedBy||null)},features:[H],decls:1,vars:0,consts:[["cdkPortalOutlet",""]],template:function(e,n){e&1&&z(0,$e,0,0,"ng-template",0)},dependencies:[et],styles:[`.cdk-dialog-container {
  display: block;
  width: 100%;
  height: 100%;
  min-height: inherit;
  max-height: inherit;
}
`],encapsulation:2})}return i})(),at=class{overlayRef;config;componentInstance=null;componentRef=null;containerInstance;disableClose;closed=new S;backdropClick;keydownEvents;outsidePointerEvents;id;_detachSubscription;constructor(o,t){this.overlayRef=o,this.config=t,this.disableClose=t.disableClose,this.backdropClick=o.backdropClick(),this.keydownEvents=o.keydownEvents(),this.outsidePointerEvents=o.outsidePointerEvents(),this.id=t.id,this.keydownEvents.subscribe(e=>{e.keyCode===27&&!this.disableClose&&!q(e)&&(e.preventDefault(),this.close(void 0,{focusOrigin:"keyboard"}))}),this.backdropClick.subscribe(()=>{!this.disableClose&&this._canClose()?this.close(void 0,{focusOrigin:"mouse"}):this.containerInstance._recaptureFocus?.()}),this._detachSubscription=o.detachments().subscribe(()=>{t.closeOnOverlayDetachments!==!1&&this.close()})}close(o,t){if(this._canClose(o)){let e=this.closed;this.containerInstance._closeInteractionType=t?.focusOrigin||"program",this._detachSubscription.unsubscribe(),this.overlayRef.dispose(),e.next(o),e.complete(),this.componentInstance=this.containerInstance=null}}updatePosition(){return this.overlayRef.updatePosition(),this}updateSize(o="",t=""){return this.overlayRef.updateSize({width:o,height:t}),this}addPanelClass(o){return this.overlayRef.addPanelClass(o),this}removePanelClass(o){return this.overlayRef.removePanelClass(o),this}_canClose(o){let t=this.config;return!!this.containerInstance&&(!t.closePredicate||t.closePredicate(o,t,this.componentInstance))}},Qe=new f("DialogScrollStrategy",{providedIn:"root",factory:()=>{let i=s(T);return()=>bt(i)}}),qe=new f("DialogData"),Ke=new f("DefaultDialogConfig");function Ze(i){let o=ct(i),t=new A;return{valueSignal:o,get value(){return o()},change:t,ngOnDestroy(){t.complete()}}}var Ft=(()=>{class i{_injector=s(T);_defaultOptions=s(Ke,{optional:!0});_parentDialog=s(i,{optional:!0,skipSelf:!0});_overlayContainer=s(me);_idGenerator=s(F);_openDialogsAtThisLevel=[];_afterAllClosedAtThisLevel=new S;_afterOpenedAtThisLevel=new S;_ariaHiddenElements=new Map;_scrollStrategy=s(Qe);get openDialogs(){return this._parentDialog?this._parentDialog.openDialogs:this._openDialogsAtThisLevel}get afterOpened(){return this._parentDialog?this._parentDialog.afterOpened:this._afterOpenedAtThisLevel}afterAllClosed=rt(()=>this.openDialogs.length?this._getAfterAllClosed():this._getAfterAllClosed().pipe(st(void 0)));constructor(){}open(t,e){let n=this._defaultOptions||new B;e=D(D({},n),e),e.id=e.id||this._idGenerator.getId("cdk-dialog-"),e.id&&this.getDialogById(e.id);let a=this._getOverlayConfig(e),r=he(this._injector,a),l=new at(r,e),d=this._attachContainer(r,l,e);if(l.containerInstance=d,!this.openDialogs.length){let c=this._overlayContainer.getContainerElement();d._focusTrapped?d._focusTrapped.pipe(G(1)).subscribe(()=>{this._hideNonDialogContentFromAssistiveTechnology(c)}):this._hideNonDialogContentFromAssistiveTechnology(c)}return this._attachDialogContent(t,l,d,e),this.openDialogs.push(l),l.closed.subscribe(()=>this._removeOpenDialog(l,!0)),this.afterOpened.next(l),l}closeAll(){Mt(this.openDialogs,t=>t.close())}getDialogById(t){return this.openDialogs.find(e=>e.id===t)}ngOnDestroy(){Mt(this._openDialogsAtThisLevel,t=>{t.config.closeOnDestroy===!1&&this._removeOpenDialog(t,!1)}),Mt(this._openDialogsAtThisLevel,t=>t.close()),this._afterAllClosedAtThisLevel.complete(),this._afterOpenedAtThisLevel.complete(),this._openDialogsAtThisLevel=[]}_getOverlayConfig(t){let e=new ge({positionStrategy:t.positionStrategy||_t().centerHorizontally().centerVertically(),scrollStrategy:t.scrollStrategy||this._scrollStrategy(),panelClass:t.panelClass,hasBackdrop:t.hasBackdrop,direction:t.direction,minWidth:t.minWidth,minHeight:t.minHeight,maxWidth:t.maxWidth,maxHeight:t.maxHeight,width:t.width,height:t.height,disposeOnNavigation:t.closeOnNavigation,disableAnimations:t.disableAnimations});return t.backdropClass&&(e.backdropClass=t.backdropClass),e}_attachContainer(t,e,n){let a=n.injector||n.viewContainerRef?.injector,r=[{provide:B,useValue:n},{provide:at,useValue:e},{provide:pe,useValue:t}],l;n.container?typeof n.container=="function"?l=n.container:(l=n.container.type,r.push(...n.container.providers(n))):l=Rt;let d=new Et(l,n.viewContainerRef,T.create({parent:a||this._injector,providers:r}));return t.attach(d).instance}_attachDialogContent(t,e,n,a){if(t instanceof $t){let r=this._createInjector(a,e,n,void 0),l={$implicit:a.data,dialogRef:e};a.templateContext&&(l=D(D({},l),typeof a.templateContext=="function"?a.templateContext():a.templateContext)),n.attachTemplatePortal(new de(t,null,l,r))}else{let r=this._createInjector(a,e,n,this._injector),l=n.attachComponentPortal(new Et(t,a.viewContainerRef,r));e.componentRef=l,e.componentInstance=l.instance}}_createInjector(t,e,n,a){let r=t.injector||t.viewContainerRef?.injector,l=[{provide:qe,useValue:t.data},{provide:at,useValue:e}];return t.providers&&(typeof t.providers=="function"?l.push(...t.providers(e,t,n)):l.push(...t.providers)),t.direction&&(!r||!r.get(tt,null,{optional:!0}))&&l.push({provide:tt,useValue:Ze(t.direction)}),T.create({parent:r||a,providers:l})}_removeOpenDialog(t,e){let n=this.openDialogs.indexOf(t);n>-1&&(this.openDialogs.splice(n,1),this.openDialogs.length||(this._ariaHiddenElements.forEach((a,r)=>{a?r.setAttribute("aria-hidden",a):r.removeAttribute("aria-hidden")}),this._ariaHiddenElements.clear(),e&&this._getAfterAllClosed().next()))}_hideNonDialogContentFromAssistiveTechnology(t){if(t.parentElement){let e=t.parentElement.children;for(let n=e.length-1;n>-1;n--){let a=e[n];a!==t&&a.nodeName!=="SCRIPT"&&a.nodeName!=="STYLE"&&!a.hasAttribute("aria-live")&&!a.hasAttribute("popover")&&(this._ariaHiddenElements.set(a,a.getAttribute("aria-hidden")),a.setAttribute("aria-hidden","true"))}}}_getAfterAllClosed(){let t=this._parentDialog;return t?t._getAfterAllClosed():this._afterAllClosedAtThisLevel}static \u0275fac=function(e){return new(e||i)};static \u0275prov=V({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})();function Mt(i,o){let t=i.length;for(;t--;)o(i[t])}var Oe=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275mod=O({type:i});static \u0275inj=w({providers:[Ft],imports:[vt,nt,ve,nt]})}return i})();function Je(i,o){}var Dt=class{viewContainerRef;injector;id;role="dialog";panelClass="";hasBackdrop=!0;backdropClass="";disableClose=!1;closePredicate;width="";height="";minWidth;minHeight;maxWidth;maxHeight;position;data=null;direction;ariaDescribedBy=null;ariaLabelledBy=null;ariaLabel=null;ariaModal=!1;autoFocus="first-tabbable";restoreFocus=!0;delayFocusTrap=!0;scrollStrategy;closeOnNavigation=!0;enterAnimationDuration;exitAnimationDuration},Bt="mdc-dialog--open",Ee="mdc-dialog--opening",Me="mdc-dialog--closing",Ye=150,Xe=75,tn=(()=>{class i extends Rt{_animationStateChanged=new A;_animationsEnabled=!it();_actionSectionCount=0;_hostElement=this._elementRef.nativeElement;_enterAnimationDuration=this._animationsEnabled?Fe(this._config.enterAnimationDuration)??Ye:0;_exitAnimationDuration=this._animationsEnabled?Fe(this._config.exitAnimationDuration)??Xe:0;_animationTimer=null;_contentAttached(){super._contentAttached(),this._startOpenAnimation()}_startOpenAnimation(){this._animationStateChanged.emit({state:"opening",totalTime:this._enterAnimationDuration}),this._animationsEnabled?(this._hostElement.style.setProperty(Re,`${this._enterAnimationDuration}ms`),this._requestAnimationFrame(()=>this._hostElement.classList.add(Ee,Bt)),this._waitForAnimationToComplete(this._enterAnimationDuration,this._finishDialogOpen)):(this._hostElement.classList.add(Bt),Promise.resolve().then(()=>this._finishDialogOpen()))}_startExitAnimation(){this._animationStateChanged.emit({state:"closing",totalTime:this._exitAnimationDuration}),this._hostElement.classList.remove(Bt),this._animationsEnabled?(this._hostElement.style.setProperty(Re,`${this._exitAnimationDuration}ms`),this._requestAnimationFrame(()=>this._hostElement.classList.add(Me)),this._waitForAnimationToComplete(this._exitAnimationDuration,this._finishDialogClose)):Promise.resolve().then(()=>this._finishDialogClose())}_updateActionSectionCount(t){this._actionSectionCount+=t,this._changeDetectorRef.markForCheck()}_finishDialogOpen=()=>{this._clearAnimationClasses(),this._openAnimationDone(this._enterAnimationDuration)};_finishDialogClose=()=>{this._clearAnimationClasses(),this._animationStateChanged.emit({state:"closed",totalTime:this._exitAnimationDuration})};_clearAnimationClasses(){this._hostElement.classList.remove(Ee,Me)}_waitForAnimationToComplete(t,e){this._animationTimer!==null&&clearTimeout(this._animationTimer),this._animationTimer=setTimeout(e,t)}_requestAnimationFrame(t){this._ngZone.runOutsideAngular(()=>{typeof requestAnimationFrame=="function"?requestAnimationFrame(t):t()})}_captureInitialFocus(){this._config.delayFocusTrap||this._trapFocus()}_openAnimationDone(t){this._config.delayFocusTrap&&this._trapFocus(),this._animationStateChanged.next({state:"opened",totalTime:t})}ngOnDestroy(){super.ngOnDestroy(),this._animationTimer!==null&&clearTimeout(this._animationTimer)}attachComponentPortal(t){let e=super.attachComponentPortal(t);return e.location.nativeElement.classList.add("mat-mdc-dialog-component-host"),e}static \u0275fac=(()=>{let t;return function(n){return(t||(t=dt(i)))(n||i)}})();static \u0275cmp=I({type:i,selectors:[["mat-dialog-container"]],hostAttrs:["tabindex","-1",1,"mat-mdc-dialog-container","mdc-dialog"],hostVars:10,hostBindings:function(e,n){e&2&&(It("id",n._config.id),m("aria-modal",n._config.ariaModal)("role",n._config.role)("aria-labelledby",n._config.ariaLabel?null:n._ariaLabelledByQueue[0])("aria-label",n._config.ariaLabel)("aria-describedby",n._config.ariaDescribedBy||null),R("_mat-animation-noopable",!n._animationsEnabled)("mat-mdc-dialog-container-with-actions",n._actionSectionCount>0))},features:[H],decls:3,vars:0,consts:[[1,"mat-mdc-dialog-inner-container","mdc-dialog__container"],[1,"mat-mdc-dialog-surface","mdc-dialog__surface"],["cdkPortalOutlet",""]],template:function(e,n){e&1&&(b(0,"div",0)(1,"div",1),z(2,Je,0,0,"ng-template",2),C()())},dependencies:[et],styles:[`.mat-mdc-dialog-container {
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
`],encapsulation:2})}return i})(),Re="--mat-dialog-transition-duration";function Fe(i){return i==null?null:typeof i=="number"?i:i.endsWith("ms")?Ot(i.substring(0,i.length-2)):i.endsWith("s")?Ot(i.substring(0,i.length-1))*1e3:i==="0"?0:null}var kt=(function(i){return i[i.OPEN=0]="OPEN",i[i.CLOSING=1]="CLOSING",i[i.CLOSED=2]="CLOSED",i})(kt||{}),ot=class{_ref;_config;_containerInstance;componentInstance;componentRef=null;disableClose;id;_afterOpened=new wt(1);_beforeClosed=new wt(1);_result;_closeFallbackTimeout;_state=kt.OPEN;_closeInteractionType;constructor(o,t,e){this._ref=o,this._config=t,this._containerInstance=e,this.disableClose=t.disableClose,this.id=o.id,o.addPanelClass("mat-mdc-dialog-panel"),e._animationStateChanged.pipe(Y(n=>n.state==="opened"),G(1)).subscribe(()=>{this._afterOpened.next(),this._afterOpened.complete()}),e._animationStateChanged.pipe(Y(n=>n.state==="closed"),G(1)).subscribe(()=>{clearTimeout(this._closeFallbackTimeout),this._finishDialogClose()}),o.overlayRef.detachments().subscribe(()=>{this._beforeClosed.next(this._result),this._beforeClosed.complete(),this._finishDialogClose()}),jt(this.backdropClick(),this.keydownEvents().pipe(Y(n=>n.keyCode===27&&!this.disableClose&&!q(n)))).subscribe(n=>{this.disableClose||(n.preventDefault(),Be(this,n.type==="keydown"?"keyboard":"mouse"))})}close(o){let t=this._config.closePredicate;t&&!t(o,this._config,this.componentInstance)||(this._result=o,this._containerInstance._animationStateChanged.pipe(Y(e=>e.state==="closing"),G(1)).subscribe(e=>{this._beforeClosed.next(o),this._beforeClosed.complete(),this._ref.overlayRef.detachBackdrop(),this._closeFallbackTimeout=setTimeout(()=>this._finishDialogClose(),e.totalTime+100)}),this._state=kt.CLOSING,this._containerInstance._startExitAnimation())}afterOpened(){return this._afterOpened}afterClosed(){return this._ref.closed}beforeClosed(){return this._beforeClosed}backdropClick(){return this._ref.backdropClick}keydownEvents(){return this._ref.keydownEvents}updatePosition(o){let t=this._ref.config.positionStrategy;return o&&(o.left||o.right)?o.left?t.left(o.left):t.right(o.right):t.centerHorizontally(),o&&(o.top||o.bottom)?o.top?t.top(o.top):t.bottom(o.bottom):t.centerVertically(),this._ref.updatePosition(),this}updateSize(o="",t=""){return this._ref.updateSize(o,t),this}addPanelClass(o){return this._ref.addPanelClass(o),this}removePanelClass(o){return this._ref.removePanelClass(o),this}getState(){return this._state}_finishDialogClose(){this._state=kt.CLOSED,this._ref.close(this._result,{focusOrigin:this._closeInteractionType}),this.componentInstance=null}};function Be(i,o,t){return i._closeInteractionType=o,i.close(t)}var en=new f("MatMdcDialogData"),nn=new f("mat-mdc-dialog-default-options"),an=new f("mat-mdc-dialog-scroll-strategy",{providedIn:"root",factory:()=>{let i=s(T);return()=>bt(i)}}),Pt=(()=>{class i{_defaultOptions=s(nn,{optional:!0});_scrollStrategy=s(an);_parentDialog=s(i,{optional:!0,skipSelf:!0});_idGenerator=s(F);_injector=s(T);_dialog=s(Ft);_animationsDisabled=it();_openDialogsAtThisLevel=[];_afterAllClosedAtThisLevel=new S;_afterOpenedAtThisLevel=new S;dialogConfigClass=Dt;_dialogRefConstructor;_dialogContainerType;_dialogDataToken;get openDialogs(){return this._parentDialog?this._parentDialog.openDialogs:this._openDialogsAtThisLevel}get afterOpened(){return this._parentDialog?this._parentDialog.afterOpened:this._afterOpenedAtThisLevel}_getAfterAllClosed(){let t=this._parentDialog;return t?t._getAfterAllClosed():this._afterAllClosedAtThisLevel}afterAllClosed=rt(()=>this.openDialogs.length?this._getAfterAllClosed():this._getAfterAllClosed().pipe(st(void 0)));constructor(){this._dialogRefConstructor=ot,this._dialogContainerType=tn,this._dialogDataToken=en}open(t,e){let n;e=D(D({},this._defaultOptions||new Dt),e),e.id=e.id||this._idGenerator.getId("mat-mdc-dialog-"),e.scrollStrategy=e.scrollStrategy||this._scrollStrategy();let a=this._dialog.open(t,Lt(D({},e),{positionStrategy:_t(this._injector).centerHorizontally().centerVertically(),disableClose:!0,closePredicate:void 0,closeOnDestroy:!1,closeOnOverlayDetachments:!1,disableAnimations:this._animationsDisabled||e.enterAnimationDuration?.toLocaleString()==="0"||e.exitAnimationDuration?.toString()==="0",container:{type:this._dialogContainerType,providers:()=>[{provide:this.dialogConfigClass,useValue:e},{provide:B,useValue:e}]},templateContext:()=>({dialogRef:n}),providers:(r,l,d)=>(n=new this._dialogRefConstructor(r,e,d),n.updatePosition(e?.position),[{provide:this._dialogContainerType,useValue:d},{provide:this._dialogDataToken,useValue:l.data},{provide:this._dialogRefConstructor,useValue:n}])}));return n.componentRef=a.componentRef,n.componentInstance=a.componentInstance,this.openDialogs.push(n),this.afterOpened.next(n),n.afterClosed().subscribe(()=>{let r=this.openDialogs.indexOf(n);r>-1&&(this.openDialogs.splice(r,1),this.openDialogs.length||this._getAfterAllClosed().next())}),n}closeAll(){this._closeDialogs(this.openDialogs)}getDialogById(t){return this.openDialogs.find(e=>e.id===t)}ngOnDestroy(){this._closeDialogs(this._openDialogsAtThisLevel),this._afterAllClosedAtThisLevel.complete(),this._afterOpenedAtThisLevel.complete()}_closeDialogs(t){let e=t.length;for(;e--;)t[e].close()}static \u0275fac=function(e){return new(e||i)};static \u0275prov=V({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})(),hi=(()=>{class i{dialogRef=s(ot,{optional:!0});_elementRef=s(x);_dialog=s(Pt);ariaLabel;type="button";dialogResult;_matDialogClose;constructor(){}ngOnInit(){this.dialogRef||(this.dialogRef=Le(this._elementRef,this._dialog.openDialogs))}ngOnChanges(t){let e=t._matDialogClose||t._matDialogCloseResult;e&&(this.dialogResult=e.currentValue)}_onButtonClick(t){Be(this.dialogRef,t.screenX===0&&t.screenY===0?"keyboard":"mouse",this.dialogResult)}static \u0275fac=function(e){return new(e||i)};static \u0275dir=E({type:i,selectors:[["","mat-dialog-close",""],["","matDialogClose",""]],hostVars:2,hostBindings:function(e,n){e&1&&U("click",function(r){return n._onButtonClick(r)}),e&2&&m("aria-label",n.ariaLabel||null)("type",n.type)},inputs:{ariaLabel:[0,"aria-label","ariaLabel"],type:"type",dialogResult:[0,"mat-dialog-close","dialogResult"],_matDialogClose:[0,"matDialogClose","_matDialogClose"]},exportAs:["matDialogClose"],features:[Wt]})}return i})(),Pe=(()=>{class i{_dialogRef=s(ot,{optional:!0});_elementRef=s(x);_dialog=s(Pt);constructor(){}ngOnInit(){this._dialogRef||(this._dialogRef=Le(this._elementRef,this._dialog.openDialogs)),this._dialogRef&&Promise.resolve().then(()=>{this._onAdd()})}ngOnDestroy(){this._dialogRef?._containerInstance&&Promise.resolve().then(()=>{this._onRemove()})}static \u0275fac=function(e){return new(e||i)};static \u0275dir=E({type:i})}return i})(),fi=(()=>{class i extends Pe{id=s(F).getId("mat-mdc-dialog-title-");_onAdd(){this._dialogRef._containerInstance?._addAriaLabelledBy?.(this.id)}_onRemove(){this._dialogRef?._containerInstance?._removeAriaLabelledBy?.(this.id)}static \u0275fac=(()=>{let t;return function(n){return(t||(t=dt(i)))(n||i)}})();static \u0275dir=E({type:i,selectors:[["","mat-dialog-title",""],["","matDialogTitle",""]],hostAttrs:[1,"mat-mdc-dialog-title","mdc-dialog__title"],hostVars:1,hostBindings:function(e,n){e&2&&It("id",n.id)},inputs:{id:"id"},exportAs:["matDialogTitle"],features:[H]})}return i})(),bi=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275dir=E({type:i,selectors:[["","mat-dialog-content",""],["mat-dialog-content"],["","matDialogContent",""]],hostAttrs:[1,"mat-mdc-dialog-content","mdc-dialog__content"],features:[qt([ce])]})}return i})(),_i=(()=>{class i extends Pe{align;_onAdd(){this._dialogRef._containerInstance?._updateActionSectionCount?.(1)}_onRemove(){this._dialogRef._containerInstance?._updateActionSectionCount?.(-1)}static \u0275fac=(()=>{let t;return function(n){return(t||(t=dt(i)))(n||i)}})();static \u0275dir=E({type:i,selectors:[["","mat-dialog-actions",""],["mat-dialog-actions"],["","matDialogActions",""]],hostAttrs:[1,"mat-mdc-dialog-actions","mdc-dialog__actions"],hostVars:6,hostBindings:function(e,n){e&2&&R("mat-mdc-dialog-actions-align-start",n.align==="start")("mat-mdc-dialog-actions-align-center",n.align==="center")("mat-mdc-dialog-actions-align-end",n.align==="end")},inputs:{align:"align"},features:[H]})}return i})();function Le(i,o){let t=i.nativeElement.parentElement;for(;t&&!t.classList.contains("mat-mdc-dialog-container");)t=t.parentElement;return t?o.find(e=>e.id===t.id):null}var vi=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275mod=O({type:i});static \u0275inj=w({providers:[Pt],imports:[Oe,vt,nt,Q]})}return i})();var un=["button"],gn=["*"];function mn(i,o){if(i&1&&(b(0,"div",2),W(1,"mat-pseudo-checkbox",6),C()),i&2){let t=gt();y(),M("disabled",t.disabled)}}var Ne=new f("MAT_BUTTON_TOGGLE_DEFAULT_OPTIONS",{providedIn:"root",factory:()=>({hideSingleSelectionIndicator:!1,hideMultipleSelectionIndicator:!1,disabledInteractive:!1})}),je=new f("MatButtonToggleGroup"),pn={provide:fe,useExisting:Gt(()=>hn),multi:!0},Tt=class{source;value;constructor(o,t){this.source=o,this.value=t}},hn=(()=>{class i{_changeDetector=s(X);_dir=s(tt,{optional:!0});_multiple=!1;_disabled=!1;_disabledInteractive=!1;_selectionModel;_rawValue;_controlValueAccessorChangeFn=()=>{};_onTouched=()=>{};_buttonToggles;appearance;get name(){return this._name}set name(t){this._name=t,this._markButtonsForCheck()}_name=s(F).getId("mat-button-toggle-group-");vertical=!1;get value(){let t=this._selectionModel?this._selectionModel.selected:[];return this.multiple?t.map(e=>e.value):t[0]?t[0].value:void 0}set value(t){this._setSelectionByValue(t),this.valueChange.emit(this.value)}valueChange=new A;get selected(){let t=this._selectionModel?this._selectionModel.selected:[];return this.multiple?t:t[0]||null}get multiple(){return this._multiple}set multiple(t){this._multiple=t,this._markButtonsForCheck()}get disabled(){return this._disabled}set disabled(t){this._disabled=t,this._markButtonsForCheck()}get disabledInteractive(){return this._disabledInteractive}set disabledInteractive(t){this._disabledInteractive=t,this._markButtonsForCheck()}get dir(){return this._dir&&this._dir.value==="rtl"?"rtl":"ltr"}change=new A;get hideSingleSelectionIndicator(){return this._hideSingleSelectionIndicator}set hideSingleSelectionIndicator(t){this._hideSingleSelectionIndicator=t,this._markButtonsForCheck()}_hideSingleSelectionIndicator;get hideMultipleSelectionIndicator(){return this._hideMultipleSelectionIndicator}set hideMultipleSelectionIndicator(t){this._hideMultipleSelectionIndicator=t,this._markButtonsForCheck()}_hideMultipleSelectionIndicator;constructor(){let t=s(Ne,{optional:!0});this.appearance=t&&t.appearance?t.appearance:"standard",this._hideSingleSelectionIndicator=t?.hideSingleSelectionIndicator??!1,this._hideMultipleSelectionIndicator=t?.hideMultipleSelectionIndicator??!1}ngOnInit(){this._selectionModel=new Se(this.multiple,void 0,!1)}ngAfterContentInit(){this._selectionModel.select(...this._buttonToggles.filter(t=>t.checked)),this.multiple||this._initializeTabIndex()}writeValue(t){this.value=t,this._changeDetector.markForCheck()}registerOnChange(t){this._controlValueAccessorChangeFn=t}registerOnTouched(t){this._onTouched=t}setDisabledState(t){this.disabled=t}_keydown(t){if(this.multiple||this.disabled||q(t))return;let n=t.target.id,a=this._buttonToggles.toArray().findIndex(l=>l.buttonId===n),r=null;switch(t.keyCode){case 32:case 13:r=this._buttonToggles.get(a)||null;break;case 38:r=this._getNextButton(a,-1);break;case 37:r=this._getNextButton(a,this.dir==="ltr"?-1:1);break;case 40:r=this._getNextButton(a,1);break;case 39:r=this._getNextButton(a,this.dir==="ltr"?1:-1);break;default:return}r&&(t.preventDefault(),r._onButtonClick(),r.focus())}_emitChangeEvent(t){let e=new Tt(t,this.value);this._rawValue=e.value,this._controlValueAccessorChangeFn(e.value),this.change.emit(e)}_syncButtonToggle(t,e,n=!1,a=!1){!this.multiple&&this.selected&&!t.checked&&(this.selected.checked=!1),this._selectionModel?e?this._selectionModel.select(t):this._selectionModel.deselect(t):a=!0,a?Promise.resolve().then(()=>this._updateModelValue(t,n)):this._updateModelValue(t,n)}_isSelected(t){return this._selectionModel&&this._selectionModel.isSelected(t)}_isPrechecked(t){return typeof this._rawValue>"u"?!1:this.multiple&&Array.isArray(this._rawValue)?this._rawValue.some(e=>t.value!=null&&e===t.value):t.value===this._rawValue}_initializeTabIndex(){if(this._buttonToggles.forEach(t=>{t.tabIndex=-1}),this.selected)this.selected.tabIndex=0;else for(let t=0;t<this._buttonToggles.length;t++){let e=this._buttonToggles.get(t);if(!e.disabled){e.tabIndex=0;break}}}_getNextButton(t,e){let n=this._buttonToggles;for(let a=1;a<=n.length;a++){let r=(t+e*a+n.length)%n.length,l=n.get(r);if(l&&!l.disabled)return l}return null}_setSelectionByValue(t){if(this._rawValue=t,!this._buttonToggles)return;let e=this._buttonToggles.toArray();if(this.multiple&&t?(Array.isArray(t),this._clearSelection(),t.forEach(n=>this._selectValue(n,e))):(this._clearSelection(),this._selectValue(t,e)),!this.multiple&&e.every(n=>n.tabIndex===-1)){for(let n of e)if(!n.disabled){n.tabIndex=0;break}}}_clearSelection(){this._selectionModel.clear(),this._buttonToggles.forEach(t=>{t.checked=!1,this.multiple||(t.tabIndex=-1)})}_selectValue(t,e){for(let n of e)if(n.value===t){n.checked=!0,this._selectionModel.select(n),this.multiple||(n.tabIndex=0);break}}_updateModelValue(t,e){e&&this._emitChangeEvent(t),this.valueChange.emit(this.value)}_markButtonsForCheck(){this._buttonToggles?.forEach(t=>t._markForCheck())}static \u0275fac=function(e){return new(e||i)};static \u0275dir=E({type:i,selectors:[["mat-button-toggle-group"]],contentQueries:function(e,n,a){if(e&1&&Xt(a,Ge,5),e&2){let r;N(r=j())&&(n._buttonToggles=r)}},hostAttrs:[1,"mat-button-toggle-group"],hostVars:6,hostBindings:function(e,n){e&1&&U("keydown",function(r){return n._keydown(r)}),e&2&&(m("role",n.multiple?"group":"radiogroup")("aria-disabled",n.disabled),R("mat-button-toggle-vertical",n.vertical)("mat-button-toggle-group-appearance-standard",n.appearance==="standard"))},inputs:{appearance:"appearance",name:"name",vertical:[2,"vertical","vertical",k],value:"value",multiple:[2,"multiple","multiple",k],disabled:[2,"disabled","disabled",k],disabledInteractive:[2,"disabledInteractive","disabledInteractive",k],hideSingleSelectionIndicator:[2,"hideSingleSelectionIndicator","hideSingleSelectionIndicator",k],hideMultipleSelectionIndicator:[2,"hideMultipleSelectionIndicator","hideMultipleSelectionIndicator",k]},outputs:{valueChange:"valueChange",change:"change"},exportAs:["matButtonToggleGroup"],features:[ee([pn,{provide:je,useExisting:i}])]})}return i})(),Ge=(()=>{class i{_changeDetectorRef=s(X);_elementRef=s(x);_focusMonitor=s(yt);_idGenerator=s(F);_animationDisabled=it();_checked=!1;ariaLabel;ariaLabelledby=null;_buttonElement;buttonToggleGroup;get buttonId(){return`${this.id}-button`}id;name;value;get tabIndex(){return this._tabIndex()}set tabIndex(t){this._tabIndex.set(t)}_tabIndex;disableRipple=!1;get appearance(){return this.buttonToggleGroup?this.buttonToggleGroup.appearance:this._appearance}set appearance(t){this._appearance=t}_appearance;get checked(){return this.buttonToggleGroup?this.buttonToggleGroup._isSelected(this):this._checked}set checked(t){t!==this._checked&&(this._checked=t,this.buttonToggleGroup&&this.buttonToggleGroup._syncButtonToggle(this,this._checked),this._changeDetectorRef.markForCheck())}get disabled(){return this._disabled||this.buttonToggleGroup&&this.buttonToggleGroup.disabled}set disabled(t){this._disabled=t}_disabled=!1;get disabledInteractive(){return this._disabledInteractive||this.buttonToggleGroup!==null&&this.buttonToggleGroup.disabledInteractive}set disabledInteractive(t){this._disabledInteractive=t}_disabledInteractive;change=new A;constructor(){s(se).load(ke);let t=s(je,{optional:!0}),e=s(new ie("tabindex"),{optional:!0})||"",n=s(Ne,{optional:!0});this._tabIndex=ct(parseInt(e)||0),this.buttonToggleGroup=t,this._appearance=n&&n.appearance?n.appearance:"standard",this._disabledInteractive=n?.disabledInteractive??!1}ngOnInit(){let t=this.buttonToggleGroup;this.id=this.id||this._idGenerator.getId("mat-button-toggle-"),t&&(t._isPrechecked(this)?this.checked=!0:t._isSelected(this)!==this._checked&&t._syncButtonToggle(this,this._checked))}ngAfterViewInit(){this._animationDisabled||this._elementRef.nativeElement.classList.add("mat-button-toggle-animations-enabled"),this._focusMonitor.monitor(this._elementRef,!0)}ngOnDestroy(){let t=this.buttonToggleGroup;this._focusMonitor.stopMonitoring(this._elementRef),t&&t._isSelected(this)&&t._syncButtonToggle(this,!1,!1,!0)}focus(t){this._buttonElement.nativeElement.focus(t)}_onButtonClick(){if(this.disabled)return;let t=this.isSingleSelector()?!0:!this._checked;if(t!==this._checked&&(this._checked=t,this.buttonToggleGroup&&(this.buttonToggleGroup._syncButtonToggle(this,this._checked,!0),this.buttonToggleGroup._onTouched())),this.isSingleSelector()){let e=this.buttonToggleGroup._buttonToggles.find(n=>n.tabIndex===0);e&&(e.tabIndex=-1),this.tabIndex=0}this.change.emit(new Tt(this,this.value))}_markForCheck(){this._changeDetectorRef.markForCheck()}_getButtonName(){return this.isSingleSelector()?this.buttonToggleGroup.name:this.name||null}isSingleSelector(){return this.buttonToggleGroup&&!this.buttonToggleGroup.multiple}static \u0275fac=function(e){return new(e||i)};static \u0275cmp=I({type:i,selectors:[["mat-button-toggle"]],viewQuery:function(e,n){if(e&1&&$(un,5),e&2){let a;N(a=j())&&(n._buttonElement=a.first)}},hostAttrs:["role","presentation",1,"mat-button-toggle"],hostVars:14,hostBindings:function(e,n){e&1&&U("focus",function(){return n.focus()}),e&2&&(m("aria-label",null)("aria-labelledby",null)("id",n.id)("name",null),R("mat-button-toggle-standalone",!n.buttonToggleGroup)("mat-button-toggle-checked",n.checked)("mat-button-toggle-disabled",n.disabled)("mat-button-toggle-disabled-interactive",n.disabledInteractive)("mat-button-toggle-appearance-standard",n.appearance==="standard"))},inputs:{ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"],id:"id",name:"name",value:"value",tabIndex:"tabIndex",disableRipple:[2,"disableRipple","disableRipple",k],appearance:"appearance",checked:[2,"checked","checked",k],disabled:[2,"disabled","disabled",k],disabledInteractive:[2,"disabledInteractive","disabledInteractive",k]},outputs:{change:"change"},exportAs:["matButtonToggle"],ngContentSelectors:gn,decls:7,vars:13,consts:[["button",""],["type","button",1,"mat-button-toggle-button","mat-focus-indicator",3,"click","id","disabled"],[1,"mat-button-toggle-checkbox-wrapper"],[1,"mat-button-toggle-label-content"],[1,"mat-button-toggle-focus-overlay"],["matRipple","",1,"mat-button-toggle-ripple",3,"matRippleTrigger","matRippleDisabled"],["state","checked","aria-hidden","true","appearance","minimal",3,"disabled"]],template:function(e,n){if(e&1&&(Jt(),b(0,"button",1,0),U("click",function(){return n._onButtonClick()}),Kt(2,mn,2,1,"div",2),b(3,"span",3),Yt(4),C()(),W(5,"span",4)(6,"span",5)),e&2){let a=mt(1);M("id",n.buttonId)("disabled",n.disabled&&!n.disabledInteractive||null),m("role",n.isSingleSelector()?"radio":"button")("tabindex",n.disabled&&!n.disabledInteractive?-1:n.tabIndex)("aria-pressed",n.isSingleSelector()?null:n.checked)("aria-checked",n.isSingleSelector()?n.checked:null)("name",n._getButtonName())("aria-label",n.ariaLabel)("aria-labelledby",n.ariaLabelledby)("aria-disabled",n.disabled&&n.disabledInteractive?"true":null),y(2),Zt(n.buttonToggleGroup&&(!n.buttonToggleGroup.multiple&&!n.buttonToggleGroup.hideSingleSelectionIndicator||n.buttonToggleGroup.multiple&&!n.buttonToggleGroup.hideMultipleSelectionIndicator)?2:-1),y(4),M("matRippleTrigger",a)("matRippleDisabled",n.disableRipple||n.disabled)}},dependencies:[Ce,we],styles:[`.mat-button-toggle-standalone,
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
`],encapsulation:2,changeDetection:0})}return i})(),zi=(()=>{class i{static \u0275fac=function(e){return new(e||i)};static \u0275mod=O({type:i});static \u0275inj=w({imports:[De,Ge,Q]})}return i})();function fn(i){return i.metadata&&(typeof i.metadata=="string"?JSON.parse(i.metadata):i.metadata).copilot_mode||null}function Ui(i){return fn(i)==="troubleshooting_injection"}var K=(function(i){return i.NETWORK_ERROR="NETWORK_ERROR",i.PROJECT_NOT_OPENED="PROJECT_NOT_OPENED",i.LLM_NOT_CONFIGURED="LLM_NOT_CONFIGURED",i.SESSION_NOT_FOUND="SESSION_NOT_FOUND",i.UNAUTHORIZED="UNAUTHORIZED",i.UNKNOWN_ERROR="UNKNOWN_ERROR",i})(K||{});var ta=(()=>{class i{http;httpController;controllerService;currentProjectId=null;currentSessionId=null;isStreaming=new Nt(!1);constructor(t,e,n){this.http=t,this.httpController=e,this.controllerService=n}injectFault(t,e,n){let a=`${this.getControllerUrl(t)}/v3/copilot/projects/${e}/chat/inject`,r=this.getAuthHeaders(t),l={"Content-Type":"application/json"};return r.keys().forEach(d=>{let c=r.get(d);c&&(l[d]=c)}),new St(d=>(fetch(a,{method:"POST",headers:l,body:JSON.stringify({message:n})}).then(async c=>{if(!c.ok){let u=`HTTP error! status: ${c.status}`;try{let h=await c.json();h.message&&(u=h.message)}catch{c.statusText&&(u=c.statusText)}let p=new Error(u);throw p.status=c.status,p.statusText=c.statusText,p.error={message:u},p}if(!c.body)throw new Error("Response body is null");let Z=c.body.getReader(),xt=new TextDecoder,P="";(async()=>{try{for(;;){let{done:u,value:p}=await Z.read();if(u){d.complete();break}P+=xt.decode(p,{stream:!0});let h=P.split(`
`);P=h.pop()||"";for(let J of h)if(J.startsWith("data: ")){let L=J.slice(6).trim();if(L)try{let g=JSON.parse(L);if(g.type==="heartbeat")continue;if(d.next(g),g.type==="done"||g.type==="error"){d.complete();break}}catch(g){console.error("Failed to parse SSE data:",L,g)}}if(d.closed)break}}catch(u){console.error("Stream processing error:",u),d.error(u)}finally{Z.cancel()}})()}).catch(c=>{console.error("Fetch error:",c),d.error(c)}),()=>{})).pipe(v(d=>_(()=>d)))}streamChat(t,e,n){this.currentProjectId=e,this.isStreaming.next(!0);let a=`${this.getControllerUrl(t)}/v3/copilot/projects/${e}/chat/stream`,r=this.getAuthHeaders(t),l={"Content-Type":"application/json"};return r.keys().forEach(d=>{let c=r.get(d);c&&(l[d]=c)}),new St(d=>(fetch(a,{method:"POST",headers:l,body:JSON.stringify(n)}).then(async c=>{if(!c.ok){let u=`HTTP error! status: ${c.status}`;try{let h=await c.json();h.message&&(u=h.message)}catch{c.statusText&&(u=c.statusText)}let p=new Error(u);throw p.status=c.status,p.statusText=c.statusText,p.error={message:u},p}if(!c.body)throw new Error("Response body is null");let Z=c.body.getReader(),xt=new TextDecoder,P="";(async()=>{try{for(;;){let{done:u,value:p}=await Z.read();if(u){d.complete();break}P+=xt.decode(p,{stream:!0});let h=P.split(`
`);P=h.pop()||"";for(let J of h)if(J.startsWith("data: ")){let L=J.slice(6).trim();if(L)try{let g=JSON.parse(L);if(g.type==="heartbeat")continue;if(g.session_id&&(this.currentSessionId=g.session_id),d.next(g),g.type==="done"||g.type==="error"){d.complete();break}}catch(g){console.error("Failed to parse SSE data:",L,g)}}if(d.closed)break}}catch(u){console.error("Stream processing error:",u),d.error(u)}finally{Z.cancel()}})()}).catch(c=>{console.error("Fetch error:",c),d.error(c)}).finally(()=>{this.isStreaming.next(!1)}),()=>{this.isStreaming.next(!1)})).pipe(v(d=>(this.isStreaming.next(!1),_(()=>d))))}getSessions(t,e){return this.httpController.get(t,`/copilot/projects/${e}/chat/sessions`).pipe(v(n=>(console.error("Failed to get sessions:",n),_(()=>n))))}getSessionHistory(t,e,n,a=100){let r=a?{limit:a}:void 0;return this.httpController.get(t,`/copilot/projects/${e}/chat/sessions/${n}/history`).pipe(v(l=>(console.error("Failed to get session history:",l),_(()=>l))))}renameSession(t,e,n,a){let r={title:a};return this.httpController.patch(t,`/copilot/projects/${e}/chat/sessions/${n}`,r).pipe(v(l=>(console.error("Failed to rename session:",l),_(()=>l))))}deleteSession(t,e,n){return this.httpController.delete(t,`/copilot/projects/${e}/chat/sessions/${n}`).pipe(v(a=>(console.error("Failed to delete session:",a),_(()=>a))))}pinSession(t,e,n){return this.httpController.put(t,`/copilot/projects/${e}/chat/sessions/${n}/pin`,null).pipe(v(a=>(console.error("Failed to pin session:",a),_(()=>a))))}unpinSession(t,e,n){return this.httpController.delete(t,`/copilot/projects/${e}/chat/sessions/${n}/pin`).pipe(v(a=>(console.error("Failed to unpin session:",a),_(()=>a))))}getStreamingState(){return this.isStreaming.asObservable()}abortChat(t,e,n){return this.httpController.post(t,`/copilot/projects/${e}/chat/sessions/${n}/abort`,null).pipe(v(a=>(console.error("Failed to abort chat:",a),_(()=>a))))}getCurrentSessionId(){return this.currentSessionId}resetCurrentSession(){this.currentSessionId=null,this.currentProjectId=null}reloadSkills(t){return this.httpController.post(t,"/copilot/reload/skills",null).pipe(v(e=>(console.error("Failed to reload skills:",e),_(()=>e))))}getControllerUrl(t){return`${t.protocol==="https:"?"https":"http"}://${t.host}:${t.port}`}getAuthHeaders(t){let e=new oe;return t.authToken?e.set("Authorization",`Bearer ${t.authToken}`):e}createChatError(t){return t.status===401?{type:K.UNAUTHORIZED,message:"Unauthorized access",details:t}:t.status===404?{type:K.SESSION_NOT_FOUND,message:"Session not found",details:t}:t.message&&t.message.includes("fetch")?{type:K.NETWORK_ERROR,message:"Network connection failed",details:t}:{type:K.UNKNOWN_ERROR,message:t.message||"Unknown error",details:t}}static \u0275fac=function(e){return new(e||i)(lt(re),lt(Te),lt(xe))};static \u0275prov=V({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})();export{wn as a,An as b,ot as c,en as d,Pt as e,hi as f,fi as g,bi as h,_i as i,vi as j,hn as k,Ge as l,zi as m,Ui as n,ta as o};
