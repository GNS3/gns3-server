import{$ as vn,A as un,Aa as Cn,Ab as d,Ad as Wn,Af as di,Bb as m,Be as oi,C as pn,Cb as Sn,Ce as Wt,Cf as mi,D as fn,Db as En,Dd as ht,De as ri,Eb as Ft,Ee as Le,Ef as hi,F as N,Fb as _e,Fc as An,Fd as Yn,G as Q,Gb as At,Gd as ut,Ha as c,Hb as g,Hd as jt,Ia as xe,Ib as H,Id as Vt,Ie as K,Ja as Ae,Jb as se,Jd as qe,Ka as wn,Kb as we,La as te,Lb as zt,Ld as $n,M as bn,N as Ge,Na as Tn,Nd as Un,Oa as ze,Od as Qn,Pa as D,Pe as si,Qa as A,Qd as qn,Ra as E,T as lt,Tc as Me,U as tt,Ua as ke,V as _n,Va as Ce,Vb as G,Vd as Kn,W as gn,Wa as dt,Wb as Te,Wc as zn,X as ee,Xa as Mn,Xc as Nn,Xe as Yt,Y as Ee,Ya as In,Yc as Bn,Ye as ce,Z as y,Za as Dn,Zc as Nt,_a as T,_e as Ie,a as j,ab as O,ad as Be,af as ot,b as Fe,ba as yn,bd as pe,ca as V,cb as P,da as F,dc as Rn,de as Xn,ea as w,eb as Rt,ef as Ke,fa as X,fb as Ot,ff as li,g as ie,ga as r,gb as Pt,gc as Pe,h as Se,hb as v,hc as $e,hd as W,i as _,ib as h,id as Bt,j as Ve,jb as u,jd as Hn,ka as ae,kb as R,kc as On,kd as it,la as oe,lb as fe,lc as nt,ma as We,mb as Oe,md as Ue,me as He,na as xn,nb as Lt,nc as Pn,ne as Zn,nf as ci,o as mn,oa as re,od as q,oe as Jn,of as ft,pa as ye,pc as U,pe as ei,qd as jn,r as et,ra as p,rb as Ne,rc as f,rd as at,re as Gt,sa as B,sb as be,sc as ge,se as ti,tb as M,tc as Ln,td as Vn,ua as Z,ub as mt,ud as Gn,va as kn,vb as x,vd as Ht,ve as ni,w as he,wa as Ye,wb as z,we as ii,xa as Re,xb as k,xd as le,xe as ai,y as hn,ya as I,yb as ue,ye as pt,za as ct,zb as $,zc as Fn,zd as Qe}from"./chunk-U3DF4UXB.js";var da=["tooltip"],ma=20;var ha=new w("mat-tooltip-scroll-strategy",{providedIn:"root",factory:()=>{let i=r(re);return()=>Qe(i,{scrollThrottle:ma})}}),ua=new w("mat-tooltip-default-options",{providedIn:"root",factory:()=>({showDelay:0,hideDelay:0,touchendHideDelay:1500})});var ui="tooltip-panel",pa={passive:!0},fa=8,ba=8,_a=24,ga=200,va=(()=>{class i{_elementRef=r(I);_ngZone=r(B);_platform=r(Be);_ariaDescriber=r(ri);_focusMonitor=r(He);_dir=r(pe);_injector=r(re);_viewContainerRef=r(ze);_mediaMatcher=r(ei);_document=r(ye);_renderer=r(te);_animationsDisabled=K();_defaultOptions=r(ua,{optional:!0});_overlayRef=null;_tooltipInstance=null;_overlayPanelClass;_portal;_position="below";_positionAtOrigin=!1;_disabled=!1;_tooltipClass;_viewInitialized=!1;_pointerExitEventsInitialized=!1;_tooltipComponent=pi;_viewportMargin=8;_currentPosition;_cssClassPrefix="mat-mdc";_ariaDescriptionPending=!1;_dirSubscribed=!1;get position(){return this._position}set position(e){e!==this._position&&(this._position=e,this._overlayRef&&(this._updatePosition(this._overlayRef),this._tooltipInstance?.show(0),this._overlayRef.updatePosition()))}get positionAtOrigin(){return this._positionAtOrigin}set positionAtOrigin(e){this._positionAtOrigin=Le(e),this._detach(),this._overlayRef=null}get disabled(){return this._disabled}set disabled(e){let t=Le(e);this._disabled!==t&&(this._disabled=t,t?this.hide(0):this._setupPointerEnterEventsIfNeeded(),this._syncAriaDescription(this.message))}get showDelay(){return this._showDelay}set showDelay(e){this._showDelay=Nt(e)}_showDelay;get hideDelay(){return this._hideDelay}set hideDelay(e){this._hideDelay=Nt(e),this._tooltipInstance&&(this._tooltipInstance._mouseLeaveHideDelay=this._hideDelay)}_hideDelay;touchGestures="auto";get message(){return this._message}set message(e){let t=this._message;this._message=e!=null?String(e).trim():"",!this._message&&this._isTooltipVisible()?this.hide(0):(this._setupPointerEnterEventsIfNeeded(),this._updateTooltipMessage()),this._syncAriaDescription(t)}_message="";get tooltipClass(){return this._tooltipClass}set tooltipClass(e){this._tooltipClass=e,this._tooltipInstance&&this._setTooltipClass(this._tooltipClass)}_eventCleanups=[];_touchstartTimeout=null;_destroyed=new _;_isDestroyed=!1;constructor(){let e=this._defaultOptions;e&&(this._showDelay=e.showDelay,this._hideDelay=e.hideDelay,e.position&&(this.position=e.position),e.positionAtOrigin&&(this.positionAtOrigin=e.positionAtOrigin),e.touchGestures&&(this.touchGestures=e.touchGestures),e.tooltipClass&&(this.tooltipClass=e.tooltipClass)),this._viewportMargin=fa}ngAfterViewInit(){this._viewInitialized=!0,this._setupPointerEnterEventsIfNeeded(),this._focusMonitor.monitor(this._elementRef).pipe(y(this._destroyed)).subscribe(e=>{e?e==="keyboard"&&this._ngZone.run(()=>this.show()):this._ngZone.run(()=>this.hide(0))})}ngOnDestroy(){let e=this._elementRef.nativeElement;this._touchstartTimeout&&clearTimeout(this._touchstartTimeout),this._overlayRef&&(this._overlayRef.dispose(),this._tooltipInstance=null),this._eventCleanups.forEach(t=>t()),this._eventCleanups.length=0,this._destroyed.next(),this._destroyed.complete(),this._isDestroyed=!0,this._ariaDescriber.removeDescription(e,this.message,"tooltip"),this._focusMonitor.stopMonitoring(e)}show(e=this.showDelay,t){if(this.disabled||!this.message||this._isTooltipVisible()){this._tooltipInstance?._cancelPendingAnimations();return}let n=this._createOverlay(t);this._detach(),this._portal=this._portal||new jn(this._tooltipComponent,this._viewContainerRef);let a=this._tooltipInstance=n.attach(this._portal).instance;a._triggerElement=this._elementRef.nativeElement,a._mouseLeaveHideDelay=this._hideDelay,a.afterHidden().pipe(y(this._destroyed)).subscribe(()=>this._detach()),this._setTooltipClass(this._tooltipClass),this._updateTooltipMessage(),a.show(e)}hide(e=this.hideDelay){let t=this._tooltipInstance;t&&(t.isVisible()?t.hide(e):(t._cancelPendingAnimations(),this._detach()))}toggle(e){this._isTooltipVisible()?this.hide():this.show(void 0,e)}_isTooltipVisible(){return!!this._tooltipInstance&&this._tooltipInstance.isVisible()}_createOverlay(e){if(this._overlayRef){let o=this._overlayRef.getConfig().positionStrategy;if((!this.positionAtOrigin||!e)&&o._origin instanceof I)return this._overlayRef;this._detach()}let t=this._injector.get(Bt).getAncestorScrollContainers(this._elementRef),n=`${this._cssClassPrefix}-${ui}`,a=ht(this._injector,this.positionAtOrigin?e||this._elementRef:this._elementRef).withTransformOriginOn(`.${this._cssClassPrefix}-tooltip`).withFlexibleDimensions(!1).withViewportMargin(this._viewportMargin).withScrollableContainers(t).withPopoverLocation("global");return a.positionChanges.pipe(y(this._destroyed)).subscribe(o=>{this._updateCurrentPositionClass(o.connectionPair),this._tooltipInstance&&o.scrollableViewProperties.isOverlayClipped&&this._tooltipInstance.isVisible()&&this._ngZone.run(()=>this.hide(0))}),this._overlayRef=ut(this._injector,{direction:this._dir,positionStrategy:a,panelClass:this._overlayPanelClass?[...this._overlayPanelClass,n]:n,scrollStrategy:this._injector.get(ha)(),disableAnimations:this._animationsDisabled,eventPredicate:this._overlayEventPredicate}),this._updatePosition(this._overlayRef),this._overlayRef.detachments().pipe(y(this._destroyed)).subscribe(()=>this._detach()),this._overlayRef.outsidePointerEvents().pipe(y(this._destroyed)).subscribe(()=>this._tooltipInstance?._handleBodyInteraction()),this._overlayRef.keydownEvents().pipe(y(this._destroyed)).subscribe(o=>{o.preventDefault(),o.stopPropagation(),this._ngZone.run(()=>this.hide(0))}),this._defaultOptions?.disableTooltipInteractivity&&this._overlayRef.addPanelClass(`${this._cssClassPrefix}-tooltip-panel-non-interactive`),this._dirSubscribed||(this._dirSubscribed=!0,this._dir.change.pipe(y(this._destroyed)).subscribe(()=>{this._overlayRef&&this._updatePosition(this._overlayRef)})),this._overlayRef}_detach(){this._overlayRef&&this._overlayRef.hasAttached()&&this._overlayRef.detach(),this._tooltipInstance=null}_updatePosition(e){let t=e.getConfig().positionStrategy,n=this._getOrigin(),a=this._getOverlayPosition();t.withPositions([this._addOffset(j(j({},n.main),a.main)),this._addOffset(j(j({},n.fallback),a.fallback))])}_addOffset(e){let t=ba,n=!this._dir||this._dir.value=="ltr";return e.originY==="top"?e.offsetY=-t:e.originY==="bottom"?e.offsetY=t:e.originX==="start"?e.offsetX=n?-t:t:e.originX==="end"&&(e.offsetX=n?t:-t),e}_getOrigin(){let e=!this._dir||this._dir.value=="ltr",t=this.position,n;t=="above"||t=="below"?n={originX:"center",originY:t=="above"?"top":"bottom"}:t=="before"||t=="left"&&e||t=="right"&&!e?n={originX:"start",originY:"center"}:(t=="after"||t=="right"&&e||t=="left"&&!e)&&(n={originX:"end",originY:"center"});let{x:a,y:o}=this._invertPosition(n.originX,n.originY);return{main:n,fallback:{originX:a,originY:o}}}_getOverlayPosition(){let e=!this._dir||this._dir.value=="ltr",t=this.position,n;t=="above"?n={overlayX:"center",overlayY:"bottom"}:t=="below"?n={overlayX:"center",overlayY:"top"}:t=="before"||t=="left"&&e||t=="right"&&!e?n={overlayX:"end",overlayY:"center"}:(t=="after"||t=="right"&&e||t=="left"&&!e)&&(n={overlayX:"start",overlayY:"center"});let{x:a,y:o}=this._invertPosition(n.overlayX,n.overlayY);return{main:n,fallback:{overlayX:a,overlayY:o}}}_updateTooltipMessage(){this._tooltipInstance&&(this._tooltipInstance.message=this.message,this._tooltipInstance._markForCheck(),xe(()=>{this._tooltipInstance&&this._overlayRef.updatePosition()},{injector:this._injector}))}_setTooltipClass(e){this._tooltipInstance&&(this._tooltipInstance.tooltipClass=e instanceof Set?Array.from(e):e,this._tooltipInstance._markForCheck())}_invertPosition(e,t){return this.position==="above"||this.position==="below"?t==="top"?t="bottom":t==="bottom"&&(t="top"):e==="end"?e="start":e==="start"&&(e="end"),{x:e,y:t}}_updateCurrentPositionClass(e){let{overlayY:t,originX:n,originY:a}=e,o;if(t==="center"?this._dir&&this._dir.value==="rtl"?o=n==="end"?"left":"right":o=n==="start"?"left":"right":o=t==="bottom"&&a==="top"?"above":"below",o!==this._currentPosition){let l=this._overlayRef;if(l){let C=`${this._cssClassPrefix}-${ui}-`;l.removePanelClass(C+this._currentPosition),l.addPanelClass(C+o)}this._currentPosition=o}}_setupPointerEnterEventsIfNeeded(){this._disabled||!this.message||!this._viewInitialized||this._eventCleanups.length||(this._isTouchPlatform()?this.touchGestures!=="off"&&(this._disableNativeGesturesIfNecessary(),this._addListener("touchstart",e=>{let t=e.targetTouches?.[0],n=t?{x:t.clientX,y:t.clientY}:void 0;this._setupPointerExitEventsIfNeeded(),this._touchstartTimeout&&clearTimeout(this._touchstartTimeout);let a=500;this._touchstartTimeout=setTimeout(()=>{this._touchstartTimeout=null,this.show(void 0,n)},this._defaultOptions?.touchLongPressShowDelay??a)})):this._addListener("mouseenter",e=>{this._setupPointerExitEventsIfNeeded();let t;e.x!==void 0&&e.y!==void 0&&(t=e),this.show(void 0,t)}))}_setupPointerExitEventsIfNeeded(){if(!this._pointerExitEventsInitialized){if(this._pointerExitEventsInitialized=!0,!this._isTouchPlatform())this._addListener("mouseleave",e=>{let t=e.relatedTarget;(!t||!this._overlayRef?.overlayElement.contains(t))&&this.hide()}),this._addListener("wheel",e=>{if(this._isTooltipVisible()){let t=this._document.elementFromPoint(e.clientX,e.clientY),n=this._elementRef.nativeElement;t!==n&&!n.contains(t)&&this.hide()}});else if(this.touchGestures!=="off"){this._disableNativeGesturesIfNecessary();let e=()=>{this._touchstartTimeout&&clearTimeout(this._touchstartTimeout),this.hide(this._defaultOptions?.touchendHideDelay)};this._addListener("touchend",e),this._addListener("touchcancel",e)}}}_addListener(e,t){this._eventCleanups.push(this._renderer.listen(this._elementRef.nativeElement,e,t,pa))}_isTouchPlatform(){let e=this._defaultOptions?.detectHoverCapability;return typeof e=="function"?!e():this._platform.IOS||this._platform.ANDROID?!0:this._platform.isBrowser?!!e&&this._mediaMatcher.matchMedia("(any-hover: none)").matches:!1}_disableNativeGesturesIfNecessary(){let e=this.touchGestures;if(e!=="off"){let t=this._elementRef.nativeElement,n=t.style;(e==="on"||t.nodeName!=="INPUT"&&t.nodeName!=="TEXTAREA")&&(n.userSelect=n.msUserSelect=n.webkitUserSelect=n.MozUserSelect="none"),(e==="on"||!t.draggable)&&(n.webkitUserDrag="none"),n.touchAction="none",n.webkitTapHighlightColor="transparent"}}_syncAriaDescription(e){this._ariaDescriptionPending||(this._ariaDescriptionPending=!0,this._ariaDescriber.removeDescription(this._elementRef.nativeElement,e,"tooltip"),this._isDestroyed||xe({write:()=>{this._ariaDescriptionPending=!1,this.message&&!this.disabled&&this._ariaDescriber.describe(this._elementRef.nativeElement,this.message,"tooltip")}},{injector:this._injector}))}_overlayEventPredicate=e=>e.type==="keydown"?this._isTooltipVisible()&&e.keyCode===27&&!le(e):!0;static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["","matTooltip",""]],hostAttrs:[1,"mat-mdc-tooltip-trigger"],hostVars:2,hostBindings:function(t,n){t&2&&g("mat-mdc-tooltip-disabled",n.disabled)},inputs:{position:[0,"matTooltipPosition","position"],positionAtOrigin:[0,"matTooltipPositionAtOrigin","positionAtOrigin"],disabled:[0,"matTooltipDisabled","disabled"],showDelay:[0,"matTooltipShowDelay","showDelay"],hideDelay:[0,"matTooltipHideDelay","hideDelay"],touchGestures:[0,"matTooltipTouchGestures","touchGestures"],message:[0,"matTooltip","message"],tooltipClass:[0,"matTooltipClass","tooltipClass"]},exportAs:["matTooltip"]})}return i})(),pi=(()=>{class i{_changeDetectorRef=r(U);_elementRef=r(I);_isMultiline=!1;message;tooltipClass;_showTimeoutId;_hideTimeoutId;_triggerElement;_mouseLeaveHideDelay;_animationsDisabled=K();_tooltip;_closeOnInteraction=!1;_isVisible=!1;_onHide=new _;_showAnimation="mat-mdc-tooltip-show";_hideAnimation="mat-mdc-tooltip-hide";constructor(){}show(e){this._hideTimeoutId!=null&&clearTimeout(this._hideTimeoutId),this._showTimeoutId=setTimeout(()=>{this._toggleVisibility(!0),this._showTimeoutId=void 0},e)}hide(e){this._showTimeoutId!=null&&clearTimeout(this._showTimeoutId),this._hideTimeoutId=setTimeout(()=>{this._toggleVisibility(!1),this._hideTimeoutId=void 0},e)}afterHidden(){return this._onHide}isVisible(){return this._isVisible}ngOnDestroy(){this._cancelPendingAnimations(),this._onHide.complete(),this._triggerElement=null}_handleBodyInteraction(){this._closeOnInteraction&&this.hide(0)}_markForCheck(){this._changeDetectorRef.markForCheck()}_handleMouseLeave({relatedTarget:e}){(!e||!this._triggerElement.contains(e))&&(this.isVisible()?this.hide(this._mouseLeaveHideDelay):this._finalizeAnimation(!1))}_onShow(){this._isMultiline=this._isTooltipMultiline(),this._markForCheck()}_isTooltipMultiline(){let e=this._elementRef.nativeElement.getBoundingClientRect();return e.height>_a&&e.width>=ga}_handleAnimationEnd({animationName:e}){(e===this._showAnimation||e===this._hideAnimation)&&this._finalizeAnimation(e===this._showAnimation)}_cancelPendingAnimations(){this._showTimeoutId!=null&&clearTimeout(this._showTimeoutId),this._hideTimeoutId!=null&&clearTimeout(this._hideTimeoutId),this._showTimeoutId=this._hideTimeoutId=void 0}_finalizeAnimation(e){e?this._closeOnInteraction=!0:this.isVisible()||this._onHide.next()}_toggleVisibility(e){let t=this._tooltip.nativeElement,n=this._showAnimation,a=this._hideAnimation;if(t.classList.remove(e?a:n),t.classList.add(e?n:a),this._isVisible!==e&&(this._isVisible=e,this._changeDetectorRef.markForCheck()),e&&!this._animationsDisabled&&typeof getComputedStyle=="function"){let o=getComputedStyle(t);(o.getPropertyValue("animation-duration")==="0s"||o.getPropertyValue("animation-name")==="none")&&(this._animationsDisabled=!0)}e&&this._onShow(),this._animationsDisabled&&(t.classList.add("_mat-animation-noopable"),this._finalizeAnimation(e))}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-tooltip-component"]],viewQuery:function(t,n){if(t&1&&$(da,7),t&2){let a;d(a=m())&&(n._tooltip=a.first)}},hostAttrs:["aria-hidden","true"],hostBindings:function(t,n){t&1&&M("mouseleave",function(o){return n._handleMouseLeave(o)})},decls:4,vars:5,consts:[["tooltip",""],[1,"mdc-tooltip","mat-mdc-tooltip",3,"animationend"],[1,"mat-mdc-tooltip-surface","mdc-tooltip__surface"]],template:function(t,n){t&1&&(fe(0,"div",1,0),mt("animationend",function(o){return n._handleAnimationEnd(o)}),fe(2,"div",2),se(3),Oe()()),t&2&&(H(n.tooltipClass),g("mdc-tooltip--multiline",n._isMultiline),c(3),we(n.message))},styles:[`.mat-mdc-tooltip {
  position: relative;
  transform: scale(0);
  display: inline-flex;
}
.mat-mdc-tooltip::before {
  content: "";
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: -1;
  position: absolute;
}
.mat-mdc-tooltip-panel-below .mat-mdc-tooltip::before {
  top: -8px;
}
.mat-mdc-tooltip-panel-above .mat-mdc-tooltip::before {
  bottom: -8px;
}
.mat-mdc-tooltip-panel-right .mat-mdc-tooltip::before {
  left: -8px;
}
.mat-mdc-tooltip-panel-left .mat-mdc-tooltip::before {
  right: -8px;
}
.mat-mdc-tooltip._mat-animation-noopable {
  animation: none;
  transform: scale(1);
}

.mat-mdc-tooltip-surface {
  word-break: normal;
  overflow-wrap: anywhere;
  padding: 4px 8px;
  min-width: 40px;
  max-width: 200px;
  min-height: 24px;
  max-height: 40vh;
  box-sizing: border-box;
  overflow: hidden;
  text-align: center;
  will-change: transform, opacity;
  background-color: var(--mat-tooltip-container-color, var(--mat-sys-inverse-surface));
  color: var(--mat-tooltip-supporting-text-color, var(--mat-sys-inverse-on-surface));
  border-radius: var(--mat-tooltip-container-shape, var(--mat-sys-corner-extra-small));
  font-family: var(--mat-tooltip-supporting-text-font, var(--mat-sys-body-small-font));
  font-size: var(--mat-tooltip-supporting-text-size, var(--mat-sys-body-small-size));
  font-weight: var(--mat-tooltip-supporting-text-weight, var(--mat-sys-body-small-weight));
  line-height: var(--mat-tooltip-supporting-text-line-height, var(--mat-sys-body-small-line-height));
  letter-spacing: var(--mat-tooltip-supporting-text-tracking, var(--mat-sys-body-small-tracking));
}
.mat-mdc-tooltip-surface::before {
  position: absolute;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
  border: 1px solid transparent;
  border-radius: inherit;
  content: "";
  pointer-events: none;
}
.mdc-tooltip--multiline .mat-mdc-tooltip-surface {
  text-align: left;
}
[dir=rtl] .mdc-tooltip--multiline .mat-mdc-tooltip-surface {
  text-align: right;
}

.mat-mdc-tooltip-panel {
  line-height: normal;
}
.mat-mdc-tooltip-panel.mat-mdc-tooltip-panel-non-interactive {
  pointer-events: none;
}

@keyframes mat-mdc-tooltip-show {
  0% {
    opacity: 0;
    transform: scale(0.8);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}
@keyframes mat-mdc-tooltip-hide {
  0% {
    opacity: 1;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(0.8);
  }
}
.mat-mdc-tooltip-show {
  animation: mat-mdc-tooltip-show 150ms cubic-bezier(0, 0, 0.2, 1) forwards;
}

.mat-mdc-tooltip-hide {
  animation: mat-mdc-tooltip-hide 75ms cubic-bezier(0.4, 0, 1, 1) forwards;
}
`],encapsulation:2,changeDetection:0})}return i})();var Kr=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[ii,qe,W,Ue]})}return i})();var ya=["mat-menu-item",""],xa=[[["mat-icon"],["","matMenuItemIcon",""]],"*"],ka=["mat-icon, [matMenuItemIcon]","*"];function Ca(i,s){i&1&&(We(),h(0,"svg",2),R(1,"polygon",3),u())}var wa=["*"];function Ta(i,s){if(i&1){let e=Ne();fe(0,"div",0),mt("click",function(){ae(e);let n=x();return oe(n.closed.emit("click"))})("animationstart",function(n){ae(e);let a=x();return oe(a._onAnimationStart(n.animationName))})("animationend",function(n){ae(e);let a=x();return oe(a._onAnimationDone(n.animationName))})("animationcancel",function(n){ae(e);let a=x();return oe(a._onAnimationDone(n.animationName))}),fe(1,"div",1),k(2),Oe()()}if(i&2){let e=x();H(e._classList),g("mat-menu-panel-animations-disabled",e._animationsDisabled)("mat-menu-panel-exit-animation",e._panelAnimationState==="void")("mat-menu-panel-animating",e._isAnimating()),be("id",e.panelId),T("aria-label",e.ariaLabel||null)("aria-labelledby",e.ariaLabelledby||null)("aria-describedby",e.ariaDescribedby||null)}}var Qt=new w("MAT_MENU_PANEL"),Ut=(()=>{class i{_elementRef=r(I);_document=r(ye);_focusMonitor=r(He);_parentMenu=r(Qt,{optional:!0});_changeDetectorRef=r(U);role="menuitem";disabled=!1;disableRipple=!1;_hovered=new _;_focused=new _;_highlighted=!1;_triggersSubmenu=!1;constructor(){r(Me).load(Ie),this._parentMenu?.addItem?.(this)}focus(e,t){this._focusMonitor&&e?this._focusMonitor.focusVia(this._getHostElement(),e,t):this._getHostElement().focus(t),this._focused.next(this)}ngAfterViewInit(){this._focusMonitor&&this._focusMonitor.monitor(this._elementRef,!1)}ngOnDestroy(){this._focusMonitor&&this._focusMonitor.stopMonitoring(this._elementRef),this._parentMenu&&this._parentMenu.removeItem&&this._parentMenu.removeItem(this),this._hovered.complete(),this._focused.complete()}_getTabIndex(){return this.disabled?"-1":"0"}_getHostElement(){return this._elementRef.nativeElement}_checkDisabled(e){this.disabled&&(e.preventDefault(),e.stopPropagation())}_handleMouseEnter(){this._hovered.next(this)}getLabel(){let e=this._elementRef.nativeElement.cloneNode(!0),t=e.querySelectorAll("mat-icon, .material-icons");for(let n=0;n<t.length;n++)t[n].remove();return e.textContent?.trim()||""}_setHighlighted(e){this._highlighted=e,this._changeDetectorRef.markForCheck()}_setTriggersSubmenu(e){this._triggersSubmenu=e,this._changeDetectorRef.markForCheck()}_hasFocus(){return this._document&&this._document.activeElement===this._getHostElement()}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["","mat-menu-item",""]],hostAttrs:[1,"mat-mdc-menu-item","mat-focus-indicator"],hostVars:8,hostBindings:function(t,n){t&1&&M("click",function(o){return n._checkDisabled(o)})("mouseenter",function(){return n._handleMouseEnter()}),t&2&&(T("role",n.role)("tabindex",n._getTabIndex())("aria-disabled",n.disabled)("disabled",n.disabled||null),g("mat-mdc-menu-item-highlighted",n._highlighted)("mat-mdc-menu-item-submenu-trigger",n._triggersSubmenu))},inputs:{role:"role",disabled:[2,"disabled","disabled",f],disableRipple:[2,"disableRipple","disableRipple",f]},exportAs:["matMenuItem"],attrs:ya,ngContentSelectors:ka,decls:5,vars:3,consts:[[1,"mat-mdc-menu-item-text"],["matRipple","",1,"mat-mdc-menu-ripple",3,"matRippleDisabled","matRippleTrigger"],["viewBox","0 0 5 10","focusable","false","aria-hidden","true",1,"mat-mdc-menu-submenu-icon"],["points","0,0 5,5 0,10"]],template:function(t,n){t&1&&(z(xa),k(0),h(1,"span",0),k(2,1),u(),R(3,"div",1),O(4,Ca,2,0,":svg:svg",2)),t&2&&(c(3),v("matRippleDisabled",n.disableRipple||n.disabled)("matRippleTrigger",n._getHostElement()),c(),P(n._triggersSubmenu?4:-1))},dependencies:[ce],encapsulation:2,changeDetection:0})}return i})();var fi=new w("MatMenuContent"),Cs=(()=>{class i{_template=r(Ae);_appRef=r(In);_injector=r(re);_viewContainerRef=r(ze);_document=r(ye);_changeDetectorRef=r(U);_portal;_outlet;_attached=new _;constructor(){}attach(e={}){this._portal||(this._portal=new at(this._template,this._viewContainerRef)),this.detach(),this._outlet||(this._outlet=new Vn(this._document.createElement("div"),this._appRef,this._injector));let t=this._template.elementRef.nativeElement;t.parentNode.insertBefore(this._outlet.outletElement,t),this._changeDetectorRef.markForCheck(),this._portal.attach(this._outlet,e),this._attached.next()}detach(){this._portal?.isAttached&&this._portal.detach()}ngOnDestroy(){this.detach(),this._outlet?.dispose()}static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["ng-template","matMenuContent",""]],features:[G([{provide:fi,useExisting:i}])]})}return i})(),Ma=new w("mat-menu-default-options",{providedIn:"root",factory:()=>({overlapTrigger:!1,xPosition:"after",yPosition:"below",backdropClass:"cdk-overlay-transparent-backdrop"})}),$t="_mat-menu-enter",bt="_mat-menu-exit",_t=(()=>{class i{_elementRef=r(I);_changeDetectorRef=r(U);_injector=r(re);_keyManager;_xPosition;_yPosition;_firstItemFocusRef;_exitFallbackTimeout;_animationsDisabled=K();_allItems;_directDescendantItems=new ct;_classList={};_panelAnimationState="void";_animationDone=new _;_isAnimating=Z(!1);parentMenu;direction;overlayPanelClass;backdropClass;ariaLabel;ariaLabelledby;ariaDescribedby;get xPosition(){return this._xPosition}set xPosition(e){this._xPosition=e,this.setPositionClasses()}get yPosition(){return this._yPosition}set yPosition(e){this._yPosition=e,this.setPositionClasses()}templateRef;items;lazyContent;overlapTrigger=!1;hasBackdrop;set panelClass(e){let t=this._previousPanelClass,n=j({},this._classList);t&&t.length&&t.split(" ").forEach(a=>{n[a]=!1}),this._previousPanelClass=e,e&&e.length&&(e.split(" ").forEach(a=>{n[a]=!0}),this._elementRef.nativeElement.className=""),this._classList=n}_previousPanelClass;get classList(){return this.panelClass}set classList(e){this.panelClass=e}closed=new p;close=this.closed;panelId=r(q).getId("mat-menu-panel-");constructor(){let e=r(Ma);this.overlayPanelClass=e.overlayPanelClass||"",this._xPosition=e.xPosition,this._yPosition=e.yPosition,this.backdropClass=e.backdropClass,this.overlapTrigger=e.overlapTrigger,this.hasBackdrop=e.hasBackdrop}ngOnInit(){this.setPositionClasses()}ngAfterContentInit(){this._updateDirectDescendants(),this._keyManager=new pt(this._directDescendantItems).withWrap().withTypeAhead().withHomeAndEnd(),this._keyManager.tabOut.subscribe(()=>this.closed.emit("tab")),this._directDescendantItems.changes.pipe(ee(this._directDescendantItems),Ee(e=>N(...e.map(t=>t._focused)))).subscribe(e=>this._keyManager.updateActiveItem(e)),this._directDescendantItems.changes.subscribe(e=>{let t=this._keyManager;if(this._panelAnimationState==="enter"&&t.activeItem?._hasFocus()){let n=e.toArray(),a=Math.max(0,Math.min(n.length-1,t.activeItemIndex||0));n[a]&&!n[a].disabled?t.setActiveItem(a):t.setNextItemActive()}})}ngOnDestroy(){this._keyManager?.destroy(),this._directDescendantItems.destroy(),this.closed.complete(),this._firstItemFocusRef?.destroy(),clearTimeout(this._exitFallbackTimeout)}_hovered(){return this._directDescendantItems.changes.pipe(ee(this._directDescendantItems),Ee(t=>N(...t.map(n=>n._hovered))))}addItem(e){}removeItem(e){}_handleKeydown(e){let t=e.keyCode,n=this._keyManager;switch(t){case 27:le(e)||(e.preventDefault(),this.closed.emit("keydown"));break;case 37:this.parentMenu&&this.direction==="ltr"&&this.closed.emit("keydown");break;case 39:this.parentMenu&&this.direction==="rtl"&&this.closed.emit("keydown");break;default:(t===38||t===40)&&n.setFocusOrigin("keyboard"),n.onKeydown(e);return}}focusFirstItem(e="program"){this._firstItemFocusRef?.destroy(),this._firstItemFocusRef=xe(()=>{let t=this._resolvePanel();if(!t||!t.contains(document.activeElement)){let n=this._keyManager;n.setFocusOrigin(e).setFirstItemActive(),!n.activeItem&&t&&t.focus()}},{injector:this._injector})}resetActiveItem(){this._keyManager.setActiveItem(-1)}setElevation(e){}setPositionClasses(e=this.xPosition,t=this.yPosition){this._classList=Fe(j({},this._classList),{"mat-menu-before":e==="before","mat-menu-after":e==="after","mat-menu-above":t==="above","mat-menu-below":t==="below"}),this._changeDetectorRef.markForCheck()}_onAnimationDone(e){let t=e===bt;(t||e===$t)&&(t&&(clearTimeout(this._exitFallbackTimeout),this._exitFallbackTimeout=void 0),this._animationDone.next(t?"void":"enter"),this._isAnimating.set(!1))}_onAnimationStart(e){(e===$t||e===bt)&&this._isAnimating.set(!0)}_setIsOpen(e){if(this._panelAnimationState=e?"enter":"void",e){if(this._keyManager.activeItemIndex===0){let t=this._resolvePanel();t&&(t.scrollTop=0)}}else this._animationsDisabled||(this._exitFallbackTimeout=setTimeout(()=>this._onAnimationDone(bt),200));this._animationsDisabled&&setTimeout(()=>{this._onAnimationDone(e?$t:bt)}),this._changeDetectorRef.markForCheck()}_updateDirectDescendants(){this._allItems.changes.pipe(ee(this._allItems)).subscribe(e=>{this._directDescendantItems.reset(e.filter(t=>t._parentMenu===this)),this._directDescendantItems.notifyOnChanges()})}_resolvePanel(){let e=null;return this._directDescendantItems.length&&(e=this._directDescendantItems.first._getHostElement().closest('[role="menu"]')),e}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-menu"]],contentQueries:function(t,n,a){if(t&1&&ue(a,fi,5)(a,Ut,5)(a,Ut,4),t&2){let o;d(o=m())&&(n.lazyContent=o.first),d(o=m())&&(n._allItems=o),d(o=m())&&(n.items=o)}},viewQuery:function(t,n){if(t&1&&$(Ae,5),t&2){let a;d(a=m())&&(n.templateRef=a.first)}},hostVars:3,hostBindings:function(t,n){t&2&&T("aria-label",null)("aria-labelledby",null)("aria-describedby",null)},inputs:{backdropClass:"backdropClass",ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"],ariaDescribedby:[0,"aria-describedby","ariaDescribedby"],xPosition:"xPosition",yPosition:"yPosition",overlapTrigger:[2,"overlapTrigger","overlapTrigger",f],hasBackdrop:[2,"hasBackdrop","hasBackdrop",e=>e==null?null:f(e)],panelClass:[0,"class","panelClass"],classList:"classList"},outputs:{closed:"closed",close:"close"},exportAs:["matMenu"],features:[G([{provide:Qt,useExisting:i}])],ngContentSelectors:wa,decls:1,vars:0,consts:[["tabindex","-1","role","menu",1,"mat-mdc-menu-panel",3,"click","animationstart","animationend","animationcancel","id"],[1,"mat-mdc-menu-content"]],template:function(t,n){t&1&&(z(),dt(0,Ta,3,12,"ng-template"))},styles:[`mat-menu {
  display: none;
}

.mat-mdc-menu-content {
  margin: 0;
  padding: 8px 0;
  outline: 0;
}
.mat-mdc-menu-content,
.mat-mdc-menu-content .mat-mdc-menu-item .mat-mdc-menu-item-text {
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  flex: 1;
  white-space: normal;
  font-family: var(--mat-menu-item-label-text-font, var(--mat-sys-label-large-font));
  line-height: var(--mat-menu-item-label-text-line-height, var(--mat-sys-label-large-line-height));
  font-size: var(--mat-menu-item-label-text-size, var(--mat-sys-label-large-size));
  letter-spacing: var(--mat-menu-item-label-text-tracking, var(--mat-sys-label-large-tracking));
  font-weight: var(--mat-menu-item-label-text-weight, var(--mat-sys-label-large-weight));
}

@keyframes _mat-menu-enter {
  from {
    opacity: 0;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@keyframes _mat-menu-exit {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}
.mat-mdc-menu-panel {
  min-width: 112px;
  max-width: 280px;
  overflow: auto;
  box-sizing: border-box;
  outline: 0;
  animation: _mat-menu-enter 120ms cubic-bezier(0, 0, 0.2, 1);
  border-radius: var(--mat-menu-container-shape, var(--mat-sys-corner-extra-small));
  background-color: var(--mat-menu-container-color, var(--mat-sys-surface-container));
  box-shadow: var(--mat-menu-container-elevation-shadow, 0px 3px 1px -2px rgba(0, 0, 0, 0.2), 0px 2px 2px 0px rgba(0, 0, 0, 0.14), 0px 1px 5px 0px rgba(0, 0, 0, 0.12));
  will-change: transform, opacity;
}
.mat-mdc-menu-panel.mat-menu-panel-exit-animation {
  animation: _mat-menu-exit 100ms 25ms linear forwards;
}
.mat-mdc-menu-panel.mat-menu-panel-animations-disabled {
  animation: none;
}
.mat-mdc-menu-panel.mat-menu-panel-animating {
  pointer-events: none;
}
.mat-mdc-menu-panel.mat-menu-panel-animating:has(.mat-mdc-menu-content:empty) {
  display: none;
}
@media (forced-colors: active) {
  .mat-mdc-menu-panel {
    outline: solid 1px;
  }
}
.mat-mdc-menu-panel .mat-divider {
  border-top-color: var(--mat-menu-divider-color, var(--mat-sys-surface-variant));
  margin-bottom: var(--mat-menu-divider-bottom-spacing, 8px);
  margin-top: var(--mat-menu-divider-top-spacing, 8px);
}

.mat-mdc-menu-item {
  display: flex;
  position: relative;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden;
  padding: 0;
  cursor: pointer;
  width: 100%;
  text-align: left;
  box-sizing: border-box;
  color: inherit;
  font-size: inherit;
  background: none;
  text-decoration: none;
  margin: 0;
  min-height: 48px;
  padding-left: var(--mat-menu-item-leading-spacing, 12px);
  padding-right: var(--mat-menu-item-trailing-spacing, 12px);
  -webkit-user-select: none;
  user-select: none;
  cursor: pointer;
  outline: none;
  border: none;
  -webkit-tap-highlight-color: transparent;
}
.mat-mdc-menu-item::-moz-focus-inner {
  border: 0;
}
[dir=rtl] .mat-mdc-menu-item {
  padding-left: var(--mat-menu-item-trailing-spacing, 12px);
  padding-right: var(--mat-menu-item-leading-spacing, 12px);
}
.mat-mdc-menu-item:has(.material-icons, mat-icon, [matButtonIcon]) {
  padding-left: var(--mat-menu-item-with-icon-leading-spacing, 12px);
  padding-right: var(--mat-menu-item-with-icon-trailing-spacing, 12px);
}
[dir=rtl] .mat-mdc-menu-item:has(.material-icons, mat-icon, [matButtonIcon]) {
  padding-left: var(--mat-menu-item-with-icon-trailing-spacing, 12px);
  padding-right: var(--mat-menu-item-with-icon-leading-spacing, 12px);
}
.mat-mdc-menu-item, .mat-mdc-menu-item:visited, .mat-mdc-menu-item:link {
  color: var(--mat-menu-item-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-menu-item .mat-icon-no-color,
.mat-mdc-menu-item .mat-mdc-menu-submenu-icon {
  color: var(--mat-menu-item-icon-color, var(--mat-sys-on-surface-variant));
}
.mat-mdc-menu-item[disabled] {
  cursor: default;
  opacity: 0.38;
}
.mat-mdc-menu-item[disabled]::after {
  display: block;
  position: absolute;
  content: "";
  top: 0;
  left: 0;
  bottom: 0;
  right: 0;
}
.mat-mdc-menu-item:focus {
  outline: 0;
}
.mat-mdc-menu-item .mat-icon {
  flex-shrink: 0;
  margin-right: var(--mat-menu-item-spacing, 12px);
  height: var(--mat-menu-item-icon-size, 24px);
  width: var(--mat-menu-item-icon-size, 24px);
}
[dir=rtl] .mat-mdc-menu-item {
  text-align: right;
}
[dir=rtl] .mat-mdc-menu-item .mat-icon {
  margin-right: 0;
  margin-left: var(--mat-menu-item-spacing, 12px);
}
.mat-mdc-menu-item:not([disabled]):hover {
  background-color: var(--mat-menu-item-hover-state-layer-color, color-mix(in srgb, var(--mat-sys-on-surface) calc(var(--mat-sys-hover-state-layer-opacity) * 100%), transparent));
}
.mat-mdc-menu-item:not([disabled]).cdk-program-focused, .mat-mdc-menu-item:not([disabled]).cdk-keyboard-focused, .mat-mdc-menu-item:not([disabled]).mat-mdc-menu-item-highlighted {
  background-color: var(--mat-menu-item-focus-state-layer-color, color-mix(in srgb, var(--mat-sys-on-surface) calc(var(--mat-sys-focus-state-layer-opacity) * 100%), transparent));
}
@media (forced-colors: active) {
  .mat-mdc-menu-item {
    margin-top: 1px;
  }
}

.mat-mdc-menu-submenu-icon {
  width: var(--mat-menu-item-icon-size, 24px);
  height: 10px;
  fill: currentColor;
  padding-left: var(--mat-menu-item-spacing, 12px);
}
[dir=rtl] .mat-mdc-menu-submenu-icon {
  padding-right: var(--mat-menu-item-spacing, 12px);
  padding-left: 0;
}
[dir=rtl] .mat-mdc-menu-submenu-icon polygon {
  transform: scaleX(-1);
  transform-origin: center;
}
@media (forced-colors: active) {
  .mat-mdc-menu-submenu-icon {
    fill: CanvasText;
  }
}

.mat-mdc-menu-item .mat-mdc-menu-ripple {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  pointer-events: none;
}
`],encapsulation:2,changeDetection:0})}return i})(),Ia=new w("mat-menu-scroll-strategy",{providedIn:"root",factory:()=>{let i=r(re);return()=>Qe(i)}});var Xe=new WeakMap,Da=(()=>{class i{_canHaveBackdrop;_element=r(I);_viewContainerRef=r(ze);_menuItemInstance=r(Ut,{optional:!0,self:!0});_dir=r(pe,{optional:!0});_focusMonitor=r(He);_ngZone=r(B);_injector=r(re);_scrollStrategy=r(Ia);_changeDetectorRef=r(U);_animationsDisabled=K();_portal;_overlayRef=null;_menuOpen=!1;_closingActionsSubscription=ie.EMPTY;_menuCloseSubscription=ie.EMPTY;_pendingRemoval;_parentMaterialMenu;_parentInnerPadding;_openedBy=void 0;get _menu(){return this._menuInternal}set _menu(e){e!==this._menuInternal&&(this._menuInternal=e,this._menuCloseSubscription.unsubscribe(),e&&(this._parentMaterialMenu,this._menuCloseSubscription=e.close.subscribe(t=>{this._destroyMenu(t),(t==="click"||t==="tab")&&this._parentMaterialMenu&&this._parentMaterialMenu.closed.emit(t)})),this._menuItemInstance?._setTriggersSubmenu(this._triggersSubmenu()))}_menuInternal=null;constructor(e){this._canHaveBackdrop=e;let t=r(Qt,{optional:!0});this._parentMaterialMenu=t instanceof _t?t:void 0}ngOnDestroy(){this._menu&&this._ownsMenu(this._menu)&&Xe.delete(this._menu),this._pendingRemoval?.unsubscribe(),this._menuCloseSubscription.unsubscribe(),this._closingActionsSubscription.unsubscribe(),this._overlayRef&&(this._overlayRef.dispose(),this._overlayRef=null)}get menuOpen(){return this._menuOpen}get dir(){return this._dir&&this._dir.value==="rtl"?"rtl":"ltr"}_triggersSubmenu(){return!!(this._menuItemInstance&&this._parentMaterialMenu&&this._menu)}_closeMenu(){this._menu?.close.emit()}_openMenu(e){if(this._triggerIsAriaDisabled())return;let t=this._menu;if(this._menuOpen||!t)return;this._pendingRemoval?.unsubscribe();let n=Xe.get(t);Xe.set(t,this),n&&n!==this&&n._closeMenu();let a=this._createOverlay(t),o=a.getConfig(),l=o.positionStrategy;this._setPosition(t,l),this._canHaveBackdrop?o.hasBackdrop=t.hasBackdrop==null?!this._triggersSubmenu():t.hasBackdrop:o.hasBackdrop=t.hasBackdrop??!1,a.hasAttached()||(a.attach(this._getPortal(t)),t.lazyContent?.attach(this.menuData)),this._closingActionsSubscription=this._menuClosingActions().subscribe(()=>this._closeMenu()),t.parentMenu=this._triggersSubmenu()?this._parentMaterialMenu:void 0,t.direction=this.dir,e&&t.focusFirstItem(this._openedBy||"program"),this._setIsMenuOpen(!0),t instanceof _t&&(t._setIsOpen(!0),t._directDescendantItems.changes.pipe(y(t.close)).subscribe(()=>{l.withLockedPosition(!1).reapplyLastPosition(),l.withLockedPosition(!0)}))}focus(e,t){this._focusMonitor&&e?this._focusMonitor.focusVia(this._element,e,t):this._element.nativeElement.focus(t)}_destroyMenu(e){let t=this._overlayRef,n=this._menu;!t||!this.menuOpen||(this._closingActionsSubscription.unsubscribe(),this._pendingRemoval?.unsubscribe(),n instanceof _t&&this._ownsMenu(n)?(this._pendingRemoval=n._animationDone.pipe(Ge(1)).subscribe(()=>{t.detach(),Xe.has(n)||n.lazyContent?.detach()}),n._setIsOpen(!1)):(t.detach(),n?.lazyContent?.detach()),n&&this._ownsMenu(n)&&Xe.delete(n),this.restoreFocus&&(e==="keydown"||!this._openedBy||!this._triggersSubmenu())&&this.focus(this._openedBy),this._openedBy=void 0,this._setIsMenuOpen(!1))}_setIsMenuOpen(e){e!==this._menuOpen&&(this._menuOpen=e,this._menuOpen?this.menuOpened.emit():this.menuClosed.emit(),this._triggersSubmenu()&&this._menuItemInstance._setHighlighted(e),this._changeDetectorRef.markForCheck())}_createOverlay(e){if(!this._overlayRef){let t=this._getOverlayConfig(e);this._subscribeToPositions(e,t.positionStrategy),this._overlayRef=ut(this._injector,t),this._overlayRef.keydownEvents().subscribe(n=>{this._menu instanceof _t&&this._menu._handleKeydown(n)})}return this._overlayRef}_getOverlayConfig(e){return new Wn({positionStrategy:ht(this._injector,this._getOverlayOrigin()).withLockedPosition().withGrowAfterOpen().withTransformOriginOn(".mat-menu-panel, .mat-mdc-menu-panel"),backdropClass:e.backdropClass||"cdk-overlay-transparent-backdrop",panelClass:e.overlayPanelClass,scrollStrategy:this._scrollStrategy(),direction:this._dir||"ltr",disableAnimations:this._animationsDisabled})}_subscribeToPositions(e,t){e.setPositionClasses&&t.positionChanges.subscribe(n=>{this._ngZone.run(()=>{let a=n.connectionPair.overlayX==="start"?"after":"before",o=n.connectionPair.overlayY==="top"?"below":"above";e.setPositionClasses(a,o)})})}_setPosition(e,t){let[n,a]=e.xPosition==="before"?["end","start"]:["start","end"],[o,l]=e.yPosition==="above"?["bottom","top"]:["top","bottom"],[C,b]=[o,l],[Y,de]=[n,a],me=0;if(this._triggersSubmenu()){if(de=n=e.xPosition==="before"?"start":"end",a=Y=n==="end"?"start":"end",this._parentMaterialMenu){if(this._parentInnerPadding==null){let S=this._parentMaterialMenu.items.first;this._parentInnerPadding=S?S._getHostElement().offsetTop:0}me=o==="bottom"?this._parentInnerPadding:-this._parentInnerPadding}}else e.overlapTrigger||(C=o==="top"?"bottom":"top",b=l==="top"?"bottom":"top");t.withPositions([{originX:n,originY:C,overlayX:Y,overlayY:o,offsetY:me},{originX:a,originY:C,overlayX:de,overlayY:o,offsetY:me},{originX:n,originY:b,overlayX:Y,overlayY:l,offsetY:-me},{originX:a,originY:b,overlayX:de,overlayY:l,offsetY:-me}])}_menuClosingActions(){let e=this._getOutsideClickStream(this._overlayRef),t=this._overlayRef.detachments(),n=this._parentMaterialMenu?this._parentMaterialMenu.closed:et(),a=this._parentMaterialMenu?this._parentMaterialMenu._hovered().pipe(Q(o=>this._menuOpen&&o!==this._menuItemInstance)):et();return N(e,n,a,t)}_getPortal(e){return(!this._portal||this._portal.templateRef!==e.templateRef)&&(this._portal=new at(e.templateRef,this._viewContainerRef)),this._portal}_ownsMenu(e){return Xe.get(e)===this}_triggerIsAriaDisabled(){return f(this._element.nativeElement.getAttribute("aria-disabled"))}static \u0275fac=function(t){Tn()};static \u0275dir=E({type:i})}return i})(),ws=(()=>{class i extends Da{_cleanupTouchstart;_hoverSubscription=ie.EMPTY;get _deprecatedMatMenuTriggerFor(){return this.menu}set _deprecatedMatMenuTriggerFor(e){this.menu=e}get menu(){return this._menu}set menu(e){this._menu=e}menuData;restoreFocus=!0;menuOpened=new p;onMenuOpen=this.menuOpened;menuClosed=new p;onMenuClose=this.menuClosed;constructor(){super(!0);let e=r(te);this._cleanupTouchstart=e.listen(this._element.nativeElement,"touchstart",t=>{Bn(t)||(this._openedBy="touch")},{passive:!0})}triggersSubmenu(){return super._triggersSubmenu()}toggleMenu(){return this.menuOpen?this.closeMenu():this.openMenu()}openMenu(){this._openMenu(!0)}closeMenu(){this._closeMenu()}updatePosition(){this._overlayRef?.updatePosition()}ngAfterContentInit(){this._handleHover()}ngOnDestroy(){super.ngOnDestroy(),this._cleanupTouchstart(),this._hoverSubscription.unsubscribe()}_getOverlayOrigin(){return this._element}_getOutsideClickStream(e){return e.backdropClick()}_handleMousedown(e){Nn(e)||(this._openedBy=e.button===0?"mouse":void 0,this.triggersSubmenu()&&e.preventDefault())}_handleKeydown(e){let t=e.keyCode;(t===13||t===32)&&(this._openedBy="keyboard"),this.triggersSubmenu()&&(t===39&&this.dir==="ltr"||t===37&&this.dir==="rtl")&&(this._openedBy="keyboard",this.openMenu())}_handleClick(e){this.triggersSubmenu()?(e.stopPropagation(),this.openMenu()):this.toggleMenu()}_handleHover(){this.triggersSubmenu()&&this._parentMaterialMenu&&(this._hoverSubscription=this._parentMaterialMenu._hovered().subscribe(e=>{e===this._menuItemInstance&&!e.disabled&&this._parentMaterialMenu?._panelAnimationState!=="void"&&(this._openedBy="mouse",this._openMenu(!1))}))}static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["","mat-menu-trigger-for",""],["","matMenuTriggerFor",""]],hostAttrs:[1,"mat-mdc-menu-trigger"],hostVars:3,hostBindings:function(t,n){t&1&&M("click",function(o){return n._handleClick(o)})("mousedown",function(o){return n._handleMousedown(o)})("keydown",function(o){return n._handleKeydown(o)}),t&2&&T("aria-haspopup",n.menu?"menu":null)("aria-expanded",n.menuOpen)("aria-controls",n.menuOpen?n.menu==null?null:n.menu.panelId:null)},inputs:{_deprecatedMatMenuTriggerFor:[0,"mat-menu-trigger-for","_deprecatedMatMenuTriggerFor"],menu:[0,"matMenuTriggerFor","menu"],menuData:[0,"matMenuTriggerData","menuData"],restoreFocus:[0,"matMenuTriggerRestoreFocus","restoreFocus"]},outputs:{menuOpened:"menuOpened",onMenuOpen:"onMenuOpen",menuClosed:"menuClosed",onMenuClose:"onMenuClose"},exportAs:["matMenuTrigger"],features:[ke]})}return i})();var Ts=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[ot,qe,W,Ue]})}return i})();var Sa=["*",[["mat-option"],["ng-container"]]],Ea=["*","mat-option, ng-container"],Ra=["text"],Oa=[[["mat-icon"]],"*"],Pa=["mat-icon","*"];function La(i,s){if(i&1&&R(0,"mat-pseudo-checkbox",1),i&2){let e=x();v("disabled",e.disabled)("state",e.selected?"checked":"unchecked")}}function Fa(i,s){if(i&1&&R(0,"mat-pseudo-checkbox",3),i&2){let e=x();v("disabled",e.disabled)}}function Aa(i,s){if(i&1&&(h(0,"span",4),se(1),u()),i&2){let e=x();c(),zt("(",e.group.label,")")}}var kt=new w("MAT_OPTION_PARENT_COMPONENT"),Ct=new w("MatOptgroup"),za=(()=>{class i{label;disabled=!1;_labelId=r(q).getId("mat-optgroup-label-");_inert;constructor(){let e=r(kt,{optional:!0});this._inert=e?.inertGroups??!1}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-optgroup"]],hostAttrs:[1,"mat-mdc-optgroup"],hostVars:3,hostBindings:function(t,n){t&2&&T("role",n._inert?null:"group")("aria-disabled",n._inert?null:n.disabled.toString())("aria-labelledby",n._inert?null:n._labelId)},inputs:{label:"label",disabled:[2,"disabled","disabled",f]},exportAs:["matOptgroup"],features:[G([{provide:Ct,useExisting:i}])],ngContentSelectors:Ea,decls:5,vars:4,consts:[["role","presentation",1,"mat-mdc-optgroup-label",3,"id"],[1,"mdc-list-item__primary-text"]],template:function(t,n){t&1&&(z(Sa),fe(0,"span",0)(1,"span",1),se(2),k(3),Oe()(),k(4,1)),t&2&&(g("mdc-list-item--disabled",n.disabled),be("id",n._labelId),c(2),zt("",n.label," "))},styles:[`.mat-mdc-optgroup {
  color: var(--mat-optgroup-label-text-color, var(--mat-sys-on-surface-variant));
  font-family: var(--mat-optgroup-label-text-font, var(--mat-sys-title-small-font));
  line-height: var(--mat-optgroup-label-text-line-height, var(--mat-sys-title-small-line-height));
  font-size: var(--mat-optgroup-label-text-size, var(--mat-sys-title-small-size));
  letter-spacing: var(--mat-optgroup-label-text-tracking, var(--mat-sys-title-small-tracking));
  font-weight: var(--mat-optgroup-label-text-weight, var(--mat-sys-title-small-weight));
}

.mat-mdc-optgroup-label {
  display: flex;
  position: relative;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden;
  min-height: 48px;
  padding: 0 16px;
  outline: none;
}
.mat-mdc-optgroup-label.mdc-list-item--disabled {
  opacity: 0.38;
}
.mat-mdc-optgroup-label .mdc-list-item__primary-text {
  font-size: inherit;
  font-weight: inherit;
  letter-spacing: inherit;
  line-height: inherit;
  font-family: inherit;
  text-decoration: inherit;
  text-transform: inherit;
  white-space: normal;
  color: inherit;
}
`],encapsulation:2,changeDetection:0})}return i})(),qt=class{source;isUserInput;constructor(s,e=!1){this.source=s,this.isUserInput=e}},wt=(()=>{class i{_element=r(I);_changeDetectorRef=r(U);_parent=r(kt,{optional:!0});group=r(Ct,{optional:!0});_signalDisableRipple=!1;_selected=!1;_active=!1;_mostRecentViewValue="";get multiple(){return this._parent&&this._parent.multiple}get selected(){return this._selected}value;id=r(q).getId("mat-option-");get disabled(){return this.group&&this.group.disabled||this._disabled()}set disabled(e){this._disabled.set(e)}_disabled=Z(!1);get disableRipple(){return this._signalDisableRipple?this._parent.disableRipple():!!this._parent?.disableRipple}get hideSingleSelectionIndicator(){return!!(this._parent&&this._parent.hideSingleSelectionIndicator)}onSelectionChange=new p;_text;_stateChanges=new _;constructor(){let e=r(Me);e.load(Ie),e.load(Jn),this._signalDisableRipple=!!this._parent&&Mn(this._parent.disableRipple)}get active(){return this._active}get viewValue(){return(this._text?.nativeElement.textContent||"").trim()}select(e=!0){this._selected||(this._selected=!0,this._changeDetectorRef.markForCheck(),e&&this._emitSelectionChangeEvent())}deselect(e=!0){this._selected&&(this._selected=!1,this._changeDetectorRef.markForCheck(),e&&this._emitSelectionChangeEvent())}focus(e,t){let n=this._getHostElement();typeof n.focus=="function"&&n.focus(t)}setActiveStyles(){this._active||(this._active=!0,this._changeDetectorRef.markForCheck())}setInactiveStyles(){this._active&&(this._active=!1,this._changeDetectorRef.markForCheck())}getLabel(){return this.viewValue}_handleKeydown(e){(e.keyCode===13||e.keyCode===32)&&!le(e)&&(this._selectViaInteraction(),e.preventDefault())}_selectViaInteraction(){this.disabled||(this._selected=this.multiple?!this._selected:!0,this._changeDetectorRef.markForCheck(),this._emitSelectionChangeEvent(!0))}_getTabIndex(){return this.disabled?"-1":"0"}_getHostElement(){return this._element.nativeElement}ngAfterViewChecked(){if(this._selected){let e=this.viewValue;e!==this._mostRecentViewValue&&(this._mostRecentViewValue&&this._stateChanges.next(),this._mostRecentViewValue=e)}}ngOnDestroy(){this._stateChanges.complete()}_emitSelectionChangeEvent(e=!1){this.onSelectionChange.emit(new qt(this,e))}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-option"]],viewQuery:function(t,n){if(t&1&&$(Ra,7),t&2){let a;d(a=m())&&(n._text=a.first)}},hostAttrs:["role","option",1,"mat-mdc-option","mdc-list-item"],hostVars:11,hostBindings:function(t,n){t&1&&M("click",function(){return n._selectViaInteraction()})("keydown",function(o){return n._handleKeydown(o)}),t&2&&(be("id",n.id),T("aria-selected",n.selected)("aria-disabled",n.disabled.toString()),g("mdc-list-item--selected",n.selected)("mat-mdc-option-multiple",n.multiple)("mat-mdc-option-active",n.active)("mdc-list-item--disabled",n.disabled))},inputs:{value:"value",id:"id",disabled:[2,"disabled","disabled",f]},outputs:{onSelectionChange:"onSelectionChange"},exportAs:["matOption"],ngContentSelectors:Pa,decls:8,vars:5,consts:[["text",""],["aria-hidden","true",1,"mat-mdc-option-pseudo-checkbox",3,"disabled","state"],[1,"mdc-list-item__primary-text"],["state","checked","aria-hidden","true","appearance","minimal",1,"mat-mdc-option-pseudo-checkbox",3,"disabled"],[1,"cdk-visually-hidden"],["aria-hidden","true","mat-ripple","",1,"mat-mdc-option-ripple","mat-focus-indicator",3,"matRippleTrigger","matRippleDisabled"]],template:function(t,n){t&1&&(z(Oa),O(0,La,1,2,"mat-pseudo-checkbox",1),k(1),h(2,"span",2,0),k(4,1),u(),O(5,Fa,1,1,"mat-pseudo-checkbox",3),O(6,Aa,2,1,"span",4),R(7,"div",5)),t&2&&(P(n.multiple?0:-1),c(5),P(!n.multiple&&n.selected&&!n.hideSingleSelectionIndicator?5:-1),c(),P(n.group&&n.group._inert?6:-1),c(),v("matRippleTrigger",n._getHostElement())("matRippleDisabled",n.disabled||n.disableRipple))},dependencies:[hi,ce],styles:[`.mat-mdc-option {
  -webkit-user-select: none;
  user-select: none;
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  display: flex;
  position: relative;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden;
  min-height: 48px;
  padding: 0 16px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  color: var(--mat-option-label-text-color, var(--mat-sys-on-surface));
  font-family: var(--mat-option-label-text-font, var(--mat-sys-label-large-font));
  line-height: var(--mat-option-label-text-line-height, var(--mat-sys-label-large-line-height));
  font-size: var(--mat-option-label-text-size, var(--mat-sys-body-large-size));
  letter-spacing: var(--mat-option-label-text-tracking, var(--mat-sys-label-large-tracking));
  font-weight: var(--mat-option-label-text-weight, var(--mat-sys-body-large-weight));
}
.mat-mdc-option:hover:not(.mdc-list-item--disabled) {
  background-color: var(--mat-option-hover-state-layer-color, color-mix(in srgb, var(--mat-sys-on-surface) calc(var(--mat-sys-hover-state-layer-opacity) * 100%), transparent));
}
.mat-mdc-option:focus.mdc-list-item, .mat-mdc-option.mat-mdc-option-active.mdc-list-item {
  background-color: var(--mat-option-focus-state-layer-color, color-mix(in srgb, var(--mat-sys-on-surface) calc(var(--mat-sys-focus-state-layer-opacity) * 100%), transparent));
  outline: 0;
}
.mat-mdc-option.mdc-list-item--selected:not(.mdc-list-item--disabled):not(.mat-mdc-option-active, .mat-mdc-option-multiple, :focus, :hover) {
  background-color: var(--mat-option-selected-state-layer-color, var(--mat-sys-secondary-container));
}
.mat-mdc-option.mdc-list-item--selected:not(.mdc-list-item--disabled):not(.mat-mdc-option-active, .mat-mdc-option-multiple, :focus, :hover) .mdc-list-item__primary-text {
  color: var(--mat-option-selected-state-label-text-color, var(--mat-sys-on-secondary-container));
}
.mat-mdc-option .mat-pseudo-checkbox {
  --mat-pseudo-checkbox-minimal-selected-checkmark-color: var(--mat-option-selected-state-label-text-color, var(--mat-sys-on-secondary-container));
}
.mat-mdc-option.mdc-list-item {
  align-items: center;
  background: transparent;
}
.mat-mdc-option.mdc-list-item--disabled {
  cursor: default;
  pointer-events: none;
}
.mat-mdc-option.mdc-list-item--disabled .mat-mdc-option-pseudo-checkbox, .mat-mdc-option.mdc-list-item--disabled .mdc-list-item__primary-text, .mat-mdc-option.mdc-list-item--disabled > mat-icon {
  opacity: 0.38;
}
.mat-mdc-optgroup .mat-mdc-option:not(.mat-mdc-option-multiple) {
  padding-left: 32px;
}
[dir=rtl] .mat-mdc-optgroup .mat-mdc-option:not(.mat-mdc-option-multiple) {
  padding-left: 16px;
  padding-right: 32px;
}
.mat-mdc-option .mat-icon,
.mat-mdc-option .mat-pseudo-checkbox-full {
  margin-right: 16px;
  flex-shrink: 0;
}
[dir=rtl] .mat-mdc-option .mat-icon,
[dir=rtl] .mat-mdc-option .mat-pseudo-checkbox-full {
  margin-right: 0;
  margin-left: 16px;
}
.mat-mdc-option .mat-pseudo-checkbox-minimal {
  margin-left: 16px;
  flex-shrink: 0;
}
[dir=rtl] .mat-mdc-option .mat-pseudo-checkbox-minimal {
  margin-right: 16px;
  margin-left: 0;
}
.mat-mdc-option .mat-mdc-option-ripple {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  pointer-events: none;
}
.mat-mdc-option .mdc-list-item__primary-text {
  white-space: normal;
  font-size: inherit;
  font-weight: inherit;
  letter-spacing: inherit;
  line-height: inherit;
  font-family: inherit;
  text-decoration: inherit;
  text-transform: inherit;
  margin-right: auto;
}
[dir=rtl] .mat-mdc-option .mdc-list-item__primary-text {
  margin-right: 0;
  margin-left: auto;
}
@media (forced-colors: active) {
  .mat-mdc-option.mdc-list-item--selected:not(:has(.mat-mdc-option-pseudo-checkbox))::after {
    content: "";
    position: absolute;
    top: 50%;
    right: 16px;
    transform: translateY(-50%);
    width: 10px;
    height: 0;
    border-bottom: solid 10px;
    border-radius: 10px;
  }
  [dir=rtl] .mat-mdc-option.mdc-list-item--selected:not(:has(.mat-mdc-option-pseudo-checkbox))::after {
    right: auto;
    left: 16px;
  }
}

.mat-mdc-option-multiple {
  --mat-list-list-item-selected-container-color: var(--mat-list-list-item-container-color, transparent);
}

.mat-mdc-option-active .mat-focus-indicator::before {
  content: "";
}
`],encapsulation:2,changeDetection:0})}return i})();function bi(i,s,e){if(e.length){let t=s.toArray(),n=e.toArray(),a=0;for(let o=0;o<i+1;o++)t[o].group&&t[o].group===n[a]&&a++;return a}return 0}function _i(i,s,e,t){return i<e?i:i+s>e+t?Math.max(0,i-t+s):e}var gi=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[W]})}return i})();var Tt=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[ot,gi,wt,W]})}return i})();var Kt=class{_box;_destroyed=new _;_resizeSubject=new _;_resizeObserver;_elementObservables=new Map;constructor(s){this._box=s,typeof ResizeObserver<"u"&&(this._resizeObserver=new ResizeObserver(e=>this._resizeSubject.next(e)))}observe(s){return this._elementObservables.has(s)||this._elementObservables.set(s,new Se(e=>{let t=this._resizeSubject.subscribe(e);return this._resizeObserver?.observe(s,{box:this._box}),()=>{this._resizeObserver?.unobserve(s),t.unsubscribe(),this._elementObservables.delete(s)}}).pipe(Q(e=>e.some(t=>t.target===s)),_n({bufferSize:1,refCount:!0}),y(this._destroyed))),this._elementObservables.get(s)}destroy(){this._destroyed.next(),this._destroyed.complete(),this._resizeSubject.complete(),this._elementObservables.clear()}},Mt=(()=>{class i{_cleanupErrorListener;_observers=new Map;_ngZone=r(B);constructor(){typeof ResizeObserver<"u"}ngOnDestroy(){for(let[,e]of this._observers)e.destroy();this._observers.clear(),this._cleanupErrorListener?.()}observe(e,t){let n=t?.box||"content-box";return this._observers.has(n)||this._observers.set(n,new Kt(n)),this._observers.get(n).observe(e)}static \u0275fac=function(t){return new(t||i)};static \u0275prov=V({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})();var Na=["notch"],Ba=["matFormFieldNotchedOutline",""],Ha=["*"],vi=["iconPrefixContainer"],yi=["textPrefixContainer"],xi=["iconSuffixContainer"],ki=["textSuffixContainer"],ja=["textField"],Va=["*",[["mat-label"]],[["","matPrefix",""],["","matIconPrefix",""]],[["","matTextPrefix",""]],[["","matTextSuffix",""]],[["","matSuffix",""],["","matIconSuffix",""]],[["mat-error"],["","matError",""]],[["mat-hint",3,"align","end"]],[["mat-hint","align","end"]]],Ga=["*","mat-label","[matPrefix], [matIconPrefix]","[matTextPrefix]","[matTextSuffix]","[matSuffix], [matIconSuffix]","mat-error, [matError]","mat-hint:not([align='end'])","mat-hint[align='end']"];function Wa(i,s){i&1&&R(0,"span",21)}function Ya(i,s){if(i&1&&(h(0,"label",20),k(1,1),O(2,Wa,1,0,"span",21),u()),i&2){let e=x(2);v("floating",e._shouldLabelFloat())("monitorResize",e._hasOutline())("id",e._labelId),T("for",e._control.disableAutomaticLabeling?null:e._control.id),c(2),P(!e.hideRequiredMarker&&e._control.required?2:-1)}}function $a(i,s){if(i&1&&O(0,Ya,3,5,"label",20),i&2){let e=x();P(e._hasFloatingLabel()?0:-1)}}function Ua(i,s){i&1&&R(0,"div",7)}function Qa(i,s){}function qa(i,s){if(i&1&&Ce(0,Qa,0,0,"ng-template",13),i&2){x(2);let e=_e(1);v("ngTemplateOutlet",e)}}function Ka(i,s){if(i&1&&(h(0,"div",9),O(1,qa,1,1,null,13),u()),i&2){let e=x();v("matFormFieldNotchedOutlineOpen",e._shouldLabelFloat()),c(),P(e._forceDisplayInfixLabel()?-1:1)}}function Xa(i,s){i&1&&(h(0,"div",10,2),k(2,2),u())}function Za(i,s){i&1&&(h(0,"div",11,3),k(2,3),u())}function Ja(i,s){}function eo(i,s){if(i&1&&Ce(0,Ja,0,0,"ng-template",13),i&2){x();let e=_e(1);v("ngTemplateOutlet",e)}}function to(i,s){i&1&&(h(0,"div",14,4),k(2,4),u())}function no(i,s){i&1&&(h(0,"div",15,5),k(2,5),u())}function io(i,s){i&1&&R(0,"div",16)}function ao(i,s){i&1&&(h(0,"div",18),k(1,6),u())}function oo(i,s){if(i&1&&(h(0,"mat-hint",22),se(1),u()),i&2){let e=x(2);v("id",e._hintLabelId),c(),we(e.hintLabel)}}function ro(i,s){if(i&1&&(h(0,"div",19),O(1,oo,2,2,"mat-hint",22),k(2,7),R(3,"div",23),k(4,8),u()),i&2){let e=x();c(),P(e.hintLabel?1:-1)}}var Xt=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["mat-label"]]})}return i})(),Si=new w("MatError"),so=(()=>{class i{id=r(q).getId("mat-mdc-error-");constructor(){}static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["mat-error"],["","matError",""]],hostAttrs:[1,"mat-mdc-form-field-error","mat-mdc-form-field-bottom-align"],hostVars:1,hostBindings:function(t,n){t&2&&be("id",n.id)},inputs:{id:"id"},features:[G([{provide:Si,useExisting:i}])]})}return i})(),Zt=(()=>{class i{align="start";id=r(q).getId("mat-mdc-hint-");static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["mat-hint"]],hostAttrs:[1,"mat-mdc-form-field-hint","mat-mdc-form-field-bottom-align"],hostVars:4,hostBindings:function(t,n){t&2&&(be("id",n.id),T("align",null),g("mat-mdc-form-field-hint-end",n.align==="end"))},inputs:{align:"align",id:"id"}})}return i})(),Ei=new w("MatPrefix"),lo=(()=>{class i{set _isTextSelector(e){this._isText=!0}_isText=!1;static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["","matPrefix",""],["","matIconPrefix",""],["","matTextPrefix",""]],inputs:{_isTextSelector:[0,"matTextPrefix","_isTextSelector"]},features:[G([{provide:Ei,useExisting:i}])]})}return i})(),Ri=new w("MatSuffix"),co=(()=>{class i{set _isTextSelector(e){this._isText=!0}_isText=!1;static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["","matSuffix",""],["","matIconSuffix",""],["","matTextSuffix",""]],inputs:{_isTextSelector:[0,"matTextSuffix","_isTextSelector"]},features:[G([{provide:Ri,useExisting:i}])]})}return i})(),Oi=new w("FloatingLabelParent"),Ci=(()=>{class i{_elementRef=r(I);get floating(){return this._floating}set floating(e){this._floating=e,this.monitorResize&&this._handleResize()}_floating=!1;get monitorResize(){return this._monitorResize}set monitorResize(e){this._monitorResize=e,this._monitorResize?this._subscribeToResize():this._resizeSubscription.unsubscribe()}_monitorResize=!1;_resizeObserver=r(Mt);_ngZone=r(B);_parent=r(Oi);_resizeSubscription=new ie;constructor(){}ngOnDestroy(){this._resizeSubscription.unsubscribe()}getWidth(){return mo(this._elementRef.nativeElement)}get element(){return this._elementRef.nativeElement}_handleResize(){setTimeout(()=>this._parent._handleLabelResized())}_subscribeToResize(){this._resizeSubscription.unsubscribe(),this._ngZone.runOutsideAngular(()=>{this._resizeSubscription=this._resizeObserver.observe(this._elementRef.nativeElement,{box:"border-box"}).subscribe(()=>this._handleResize())})}static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["label","matFormFieldFloatingLabel",""]],hostAttrs:[1,"mdc-floating-label","mat-mdc-floating-label"],hostVars:2,hostBindings:function(t,n){t&2&&g("mdc-floating-label--float-above",n.floating)},inputs:{floating:"floating",monitorResize:"monitorResize"}})}return i})();function mo(i){let s=i;if(s.offsetParent!==null)return s.scrollWidth;let e=s.cloneNode(!0);e.style.setProperty("position","absolute"),e.style.setProperty("transform","translate(-9999px, -9999px)"),document.documentElement.appendChild(e);let t=e.scrollWidth;return e.remove(),t}var wi="mdc-line-ripple--active",It="mdc-line-ripple--deactivating",Ti=(()=>{class i{_elementRef=r(I);_cleanupTransitionEnd;constructor(){let e=r(B),t=r(te);e.runOutsideAngular(()=>{this._cleanupTransitionEnd=t.listen(this._elementRef.nativeElement,"transitionend",this._handleTransitionEnd)})}activate(){let e=this._elementRef.nativeElement.classList;e.remove(It),e.add(wi)}deactivate(){this._elementRef.nativeElement.classList.add(It)}_handleTransitionEnd=e=>{let t=this._elementRef.nativeElement.classList,n=t.contains(It);e.propertyName==="opacity"&&n&&t.remove(wi,It)};ngOnDestroy(){this._cleanupTransitionEnd()}static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["div","matFormFieldLineRipple",""]],hostAttrs:[1,"mdc-line-ripple"]})}return i})(),Mi=(()=>{class i{_elementRef=r(I);_ngZone=r(B);open=!1;_notch;ngAfterViewInit(){let e=this._elementRef.nativeElement,t=e.querySelector(".mdc-floating-label");t?(e.classList.add("mdc-notched-outline--upgraded"),typeof requestAnimationFrame=="function"&&(t.style.transitionDuration="0s",this._ngZone.runOutsideAngular(()=>{requestAnimationFrame(()=>t.style.transitionDuration="")}))):e.classList.add("mdc-notched-outline--no-label")}_setNotchWidth(e){let t=this._notch.nativeElement;!this.open||!e?t.style.width="":t.style.width=`calc(${e}px * var(--mat-mdc-form-field-floating-label-scale, 0.75) + 9px)`}_setMaxWidth(e){this._notch.nativeElement.style.setProperty("--mat-form-field-notch-max-width",`calc(100% - ${e}px)`)}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["div","matFormFieldNotchedOutline",""]],viewQuery:function(t,n){if(t&1&&$(Na,5),t&2){let a;d(a=m())&&(n._notch=a.first)}},hostAttrs:[1,"mdc-notched-outline"],hostVars:2,hostBindings:function(t,n){t&2&&g("mdc-notched-outline--notched",n.open)},inputs:{open:[0,"matFormFieldNotchedOutlineOpen","open"]},attrs:Ba,ngContentSelectors:Ha,decls:5,vars:0,consts:[["notch",""],[1,"mat-mdc-notch-piece","mdc-notched-outline__leading"],[1,"mat-mdc-notch-piece","mdc-notched-outline__notch"],[1,"mat-mdc-notch-piece","mdc-notched-outline__trailing"]],template:function(t,n){t&1&&(z(),Lt(0,"div",1),fe(1,"div",2,0),k(3),Oe(),Lt(4,"div",3))},encapsulation:2,changeDetection:0})}return i})(),Jt=(()=>{class i{value=null;stateChanges;id;placeholder;ngControl=null;focused=!1;empty=!1;shouldLabelFloat=!1;required=!1;disabled=!1;errorState=!1;controlType;autofilled;userAriaDescribedBy;disableAutomaticLabeling;describedByIds;static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i})}return i})();var en=new w("MatFormField"),ho=new w("MAT_FORM_FIELD_DEFAULT_OPTIONS"),Ii="fill",uo="auto",Di="fixed",po="translateY(-50%)",Pi=(()=>{class i{_elementRef=r(I);_changeDetectorRef=r(U);_platform=r(Be);_idGenerator=r(q);_ngZone=r(B);_defaults=r(ho,{optional:!0});_currentDirection;_textField;_iconPrefixContainer;_textPrefixContainer;_iconSuffixContainer;_textSuffixContainer;_floatingLabel;_notchedOutline;_lineRipple;_iconPrefixContainerSignal=nt("iconPrefixContainer");_textPrefixContainerSignal=nt("textPrefixContainer");_iconSuffixContainerSignal=nt("iconSuffixContainer");_textSuffixContainerSignal=nt("textSuffixContainer");_prefixSuffixContainers=Pe(()=>[this._iconPrefixContainerSignal(),this._textPrefixContainerSignal(),this._iconSuffixContainerSignal(),this._textSuffixContainerSignal()].map(e=>e?.nativeElement).filter(e=>e!==void 0));_formFieldControl;_prefixChildren;_suffixChildren;_errorChildren;_hintChildren;_labelChild=Pn(Xt);get hideRequiredMarker(){return this._hideRequiredMarker}set hideRequiredMarker(e){this._hideRequiredMarker=Le(e)}_hideRequiredMarker=!1;color="primary";get floatLabel(){return this._floatLabel||this._defaults?.floatLabel||uo}set floatLabel(e){e!==this._floatLabel&&(this._floatLabel=e,this._changeDetectorRef.markForCheck())}_floatLabel;get appearance(){return this._appearanceSignal()}set appearance(e){let t=e||this._defaults?.appearance||Ii;this._appearanceSignal.set(t)}_appearanceSignal=Z(Ii);get subscriptSizing(){return this._subscriptSizing||this._defaults?.subscriptSizing||Di}set subscriptSizing(e){this._subscriptSizing=e||this._defaults?.subscriptSizing||Di}_subscriptSizing=null;get hintLabel(){return this._hintLabel}set hintLabel(e){this._hintLabel=e,this._processHints()}_hintLabel="";_hasIconPrefix=!1;_hasTextPrefix=!1;_hasIconSuffix=!1;_hasTextSuffix=!1;_labelId=this._idGenerator.getId("mat-mdc-form-field-label-");_hintLabelId=this._idGenerator.getId("mat-mdc-hint-");_describedByIds;get _control(){return this._explicitFormFieldControl||this._formFieldControl}set _control(e){this._explicitFormFieldControl=e}_destroyed=new _;_isFocused=null;_explicitFormFieldControl;_previousControl=null;_previousControlValidatorFn=null;_stateChanges;_valueChanges;_describedByChanges;_outlineLabelOffsetResizeObserver=null;_animationsDisabled=K();constructor(){let e=this._defaults,t=r(pe);e&&(e.appearance&&(this.appearance=e.appearance),this._hideRequiredMarker=!!e?.hideRequiredMarker,e.color&&(this.color=e.color)),kn(()=>this._currentDirection=t.valueSignal()),this._syncOutlineLabelOffset()}ngAfterViewInit(){this._updateFocusState(),this._animationsDisabled||this._ngZone.runOutsideAngular(()=>{setTimeout(()=>{this._elementRef.nativeElement.classList.add("mat-form-field-animations-enabled")},300)}),this._changeDetectorRef.detectChanges()}ngAfterContentInit(){this._assertFormFieldControl(),this._initializeSubscript(),this._initializePrefixAndSuffix()}ngAfterContentChecked(){this._assertFormFieldControl(),this._control!==this._previousControl&&(this._initializeControl(this._previousControl),this._control.ngControl&&this._control.ngControl.control&&(this._previousControlValidatorFn=this._control.ngControl.control.validator),this._previousControl=this._control),this._control.ngControl&&this._control.ngControl.control&&this._control.ngControl.control.validator!==this._previousControlValidatorFn&&this._changeDetectorRef.markForCheck()}ngOnDestroy(){this._outlineLabelOffsetResizeObserver?.disconnect(),this._stateChanges?.unsubscribe(),this._valueChanges?.unsubscribe(),this._describedByChanges?.unsubscribe(),this._destroyed.next(),this._destroyed.complete()}getLabelId=Pe(()=>this._hasFloatingLabel()?this._labelId:null);getConnectedOverlayOrigin(){return this._textField||this._elementRef}_animateAndLockLabel(){this._hasFloatingLabel()&&(this.floatLabel="always")}_initializeControl(e){let t=this._control,n="mat-mdc-form-field-type-";e&&this._elementRef.nativeElement.classList.remove(n+e.controlType),t.controlType&&this._elementRef.nativeElement.classList.add(n+t.controlType),this._stateChanges?.unsubscribe(),this._stateChanges=t.stateChanges.subscribe(()=>{this._updateFocusState(),this._changeDetectorRef.markForCheck()}),this._describedByChanges?.unsubscribe(),this._describedByChanges=t.stateChanges.pipe(ee([void 0,void 0]),he(()=>[t.errorState,t.userAriaDescribedBy]),lt(),Q(([[a,o],[l,C]])=>a!==l||o!==C)).subscribe(()=>this._syncDescribedByIds()),this._valueChanges?.unsubscribe(),t.ngControl&&t.ngControl.valueChanges&&(this._valueChanges=t.ngControl.valueChanges.pipe(y(this._destroyed)).subscribe(()=>this._changeDetectorRef.markForCheck()))}_checkPrefixAndSuffixTypes(){this._hasIconPrefix=!!this._prefixChildren.find(e=>!e._isText),this._hasTextPrefix=!!this._prefixChildren.find(e=>e._isText),this._hasIconSuffix=!!this._suffixChildren.find(e=>!e._isText),this._hasTextSuffix=!!this._suffixChildren.find(e=>e._isText)}_initializePrefixAndSuffix(){this._checkPrefixAndSuffixTypes(),N(this._prefixChildren.changes,this._suffixChildren.changes).subscribe(()=>{this._checkPrefixAndSuffixTypes(),this._changeDetectorRef.markForCheck()})}_initializeSubscript(){this._hintChildren.changes.subscribe(()=>{this._processHints(),this._changeDetectorRef.markForCheck()}),this._errorChildren.changes.subscribe(()=>{this._syncDescribedByIds(),this._changeDetectorRef.markForCheck()}),this._validateHints(),this._syncDescribedByIds()}_assertFormFieldControl(){this._control}_updateFocusState(){let e=this._control.focused;e&&!this._isFocused?(this._isFocused=!0,this._lineRipple?.activate()):!e&&(this._isFocused||this._isFocused===null)&&(this._isFocused=!1,this._lineRipple?.deactivate()),this._elementRef.nativeElement.classList.toggle("mat-focused",e),this._textField?.nativeElement.classList.toggle("mdc-text-field--focused",e)}_syncOutlineLabelOffset(){Ln({earlyRead:()=>{if(this._appearanceSignal()!=="outline")return this._outlineLabelOffsetResizeObserver?.disconnect(),null;if(globalThis.ResizeObserver){this._outlineLabelOffsetResizeObserver||=new globalThis.ResizeObserver(()=>{this._writeOutlinedLabelStyles(this._getOutlinedLabelOffset())});for(let e of this._prefixSuffixContainers())this._outlineLabelOffsetResizeObserver.observe(e,{box:"border-box"})}return this._getOutlinedLabelOffset()},write:e=>this._writeOutlinedLabelStyles(e())})}_shouldAlwaysFloat(){return this.floatLabel==="always"}_hasOutline(){return this.appearance==="outline"}_forceDisplayInfixLabel(){return!this._platform.isBrowser&&this._prefixChildren.length&&!this._shouldLabelFloat()}_hasFloatingLabel=Pe(()=>!!this._labelChild());_shouldLabelFloat(){return this._hasFloatingLabel()?this._control.shouldLabelFloat||this._shouldAlwaysFloat():!1}_shouldForward(e){let t=this._control?this._control.ngControl:null;return t&&t[e]}_getSubscriptMessageType(){return this._errorChildren&&this._errorChildren.length>0&&this._control.errorState?"error":"hint"}_handleLabelResized(){this._refreshOutlineNotchWidth()}_refreshOutlineNotchWidth(){!this._hasOutline()||!this._floatingLabel||!this._shouldLabelFloat()?this._notchedOutline?._setNotchWidth(0):this._notchedOutline?._setNotchWidth(this._floatingLabel.getWidth())}_processHints(){this._validateHints(),this._syncDescribedByIds()}_validateHints(){this._hintChildren}_syncDescribedByIds(){if(this._control){let e=[];if(this._control.userAriaDescribedBy&&typeof this._control.userAriaDescribedBy=="string"&&e.push(...this._control.userAriaDescribedBy.split(" ")),this._getSubscriptMessageType()==="hint"){let a=this._hintChildren?this._hintChildren.find(l=>l.align==="start"):null,o=this._hintChildren?this._hintChildren.find(l=>l.align==="end"):null;a?e.push(a.id):this._hintLabel&&e.push(this._hintLabelId),o&&e.push(o.id)}else this._errorChildren&&e.push(...this._errorChildren.map(a=>a.id));let t=this._control.describedByIds,n;if(t){let a=this._describedByIds||e;n=e.concat(t.filter(o=>o&&!a.includes(o)))}else n=e;this._control.setDescribedByIds(n),this._describedByIds=e}}_getOutlinedLabelOffset(){if(!this._hasOutline()||!this._floatingLabel)return null;if(!this._iconPrefixContainer&&!this._textPrefixContainer)return["",null];if(!this._isAttachedToDom())return null;let e=this._iconPrefixContainer?.nativeElement,t=this._textPrefixContainer?.nativeElement,n=this._iconSuffixContainer?.nativeElement,a=this._textSuffixContainer?.nativeElement,o=e?.getBoundingClientRect().width??0,l=t?.getBoundingClientRect().width??0,C=n?.getBoundingClientRect().width??0,b=a?.getBoundingClientRect().width??0,Y=this._currentDirection==="rtl"?"-1":"1",de=`${o+l}px`,S=`calc(${Y} * (${de} + var(--mat-mdc-form-field-label-offset-x, 0px)))`,ne=`var(--mat-mdc-form-field-label-transform, ${po} translateX(${S}))`,st=o+l+C+b;return[ne,st]}_writeOutlinedLabelStyles(e){if(e!==null){let[t,n]=e;this._floatingLabel&&(this._floatingLabel.element.style.transform=t),n!==null&&this._notchedOutline?._setMaxWidth(n)}}_isAttachedToDom(){let e=this._elementRef.nativeElement;if(e.getRootNode){let t=e.getRootNode();return t&&t!==e}return document.documentElement.contains(e)}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-form-field"]],contentQueries:function(t,n,a){if(t&1&&(Sn(a,n._labelChild,Xt,5),ue(a,Jt,5)(a,Ei,5)(a,Ri,5)(a,Si,5)(a,Zt,5)),t&2){Ft();let o;d(o=m())&&(n._formFieldControl=o.first),d(o=m())&&(n._prefixChildren=o),d(o=m())&&(n._suffixChildren=o),d(o=m())&&(n._errorChildren=o),d(o=m())&&(n._hintChildren=o)}},viewQuery:function(t,n){if(t&1&&(En(n._iconPrefixContainerSignal,vi,5)(n._textPrefixContainerSignal,yi,5)(n._iconSuffixContainerSignal,xi,5)(n._textSuffixContainerSignal,ki,5),$(ja,5)(vi,5)(yi,5)(xi,5)(ki,5)(Ci,5)(Mi,5)(Ti,5)),t&2){Ft(4);let a;d(a=m())&&(n._textField=a.first),d(a=m())&&(n._iconPrefixContainer=a.first),d(a=m())&&(n._textPrefixContainer=a.first),d(a=m())&&(n._iconSuffixContainer=a.first),d(a=m())&&(n._textSuffixContainer=a.first),d(a=m())&&(n._floatingLabel=a.first),d(a=m())&&(n._notchedOutline=a.first),d(a=m())&&(n._lineRipple=a.first)}},hostAttrs:[1,"mat-mdc-form-field"],hostVars:38,hostBindings:function(t,n){t&2&&g("mat-mdc-form-field-label-always-float",n._shouldAlwaysFloat())("mat-mdc-form-field-has-icon-prefix",n._hasIconPrefix)("mat-mdc-form-field-has-icon-suffix",n._hasIconSuffix)("mat-form-field-invalid",n._control.errorState)("mat-form-field-disabled",n._control.disabled)("mat-form-field-autofilled",n._control.autofilled)("mat-form-field-appearance-fill",n.appearance=="fill")("mat-form-field-appearance-outline",n.appearance=="outline")("mat-form-field-hide-placeholder",n._hasFloatingLabel()&&!n._shouldLabelFloat())("mat-primary",n.color!=="accent"&&n.color!=="warn")("mat-accent",n.color==="accent")("mat-warn",n.color==="warn")("ng-untouched",n._shouldForward("untouched"))("ng-touched",n._shouldForward("touched"))("ng-pristine",n._shouldForward("pristine"))("ng-dirty",n._shouldForward("dirty"))("ng-valid",n._shouldForward("valid"))("ng-invalid",n._shouldForward("invalid"))("ng-pending",n._shouldForward("pending"))},inputs:{hideRequiredMarker:"hideRequiredMarker",color:"color",floatLabel:"floatLabel",appearance:"appearance",subscriptSizing:"subscriptSizing",hintLabel:"hintLabel"},exportAs:["matFormField"],features:[G([{provide:en,useExisting:i},{provide:Oi,useExisting:i}])],ngContentSelectors:Ga,decls:18,vars:21,consts:[["labelTemplate",""],["textField",""],["iconPrefixContainer",""],["textPrefixContainer",""],["textSuffixContainer",""],["iconSuffixContainer",""],[1,"mat-mdc-text-field-wrapper","mdc-text-field",3,"click"],[1,"mat-mdc-form-field-focus-overlay"],[1,"mat-mdc-form-field-flex"],["matFormFieldNotchedOutline","",3,"matFormFieldNotchedOutlineOpen"],[1,"mat-mdc-form-field-icon-prefix"],[1,"mat-mdc-form-field-text-prefix"],[1,"mat-mdc-form-field-infix"],[3,"ngTemplateOutlet"],[1,"mat-mdc-form-field-text-suffix"],[1,"mat-mdc-form-field-icon-suffix"],["matFormFieldLineRipple",""],["aria-atomic","true","aria-live","polite",1,"mat-mdc-form-field-subscript-wrapper","mat-mdc-form-field-bottom-align"],[1,"mat-mdc-form-field-error-wrapper"],[1,"mat-mdc-form-field-hint-wrapper"],["matFormFieldFloatingLabel","",3,"floating","monitorResize","id"],["aria-hidden","true",1,"mat-mdc-form-field-required-marker","mdc-floating-label--required"],[3,"id"],[1,"mat-mdc-form-field-hint-spacer"]],template:function(t,n){if(t&1&&(z(Va),Ce(0,$a,1,1,"ng-template",null,0,Rn),h(2,"div",6,1),M("click",function(o){return n._control.onContainerClick(o)}),O(4,Ua,1,0,"div",7),h(5,"div",8),O(6,Ka,2,2,"div",9),O(7,Xa,3,0,"div",10),O(8,Za,3,0,"div",11),h(9,"div",12),O(10,eo,1,1,null,13),k(11),u(),O(12,to,3,0,"div",14),O(13,no,3,0,"div",15),u(),O(14,io,1,0,"div",16),u(),h(15,"div",17),O(16,ao,2,0,"div",18)(17,ro,5,1,"div",19),u()),t&2){let a;c(2),g("mdc-text-field--filled",!n._hasOutline())("mdc-text-field--outlined",n._hasOutline())("mdc-text-field--no-label",!n._hasFloatingLabel())("mdc-text-field--disabled",n._control.disabled)("mdc-text-field--invalid",n._control.errorState),c(2),P(!n._hasOutline()&&!n._control.disabled?4:-1),c(2),P(n._hasOutline()?6:-1),c(),P(n._hasIconPrefix?7:-1),c(),P(n._hasTextPrefix?8:-1),c(2),P(!n._hasOutline()||n._forceDisplayInfixLabel()?10:-1),c(2),P(n._hasTextSuffix?12:-1),c(),P(n._hasIconSuffix?13:-1),c(),P(n._hasOutline()?-1:14),c(),g("mat-mdc-form-field-subscript-dynamic-size",n.subscriptSizing==="dynamic");let o=n._getSubscriptMessageType();c(),P((a=o)==="error"?16:a==="hint"?17:-1)}},dependencies:[Ci,Mi,Fn,Ti,Zt],styles:[`.mdc-text-field {
  display: inline-flex;
  align-items: baseline;
  padding: 0 16px;
  position: relative;
  box-sizing: border-box;
  overflow: hidden;
  will-change: opacity, transform, color;
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
  border-bottom-right-radius: 0;
  border-bottom-left-radius: 0;
}

.mdc-text-field__input {
  width: 100%;
  min-width: 0;
  border: none;
  border-radius: 0;
  background: none;
  padding: 0;
  -moz-appearance: none;
  -webkit-appearance: none;
  height: 28px;
}
.mdc-text-field__input::-webkit-calendar-picker-indicator, .mdc-text-field__input::-webkit-search-cancel-button {
  display: none;
}
.mdc-text-field__input::-ms-clear {
  display: none;
}
.mdc-text-field__input:focus {
  outline: none;
}
.mdc-text-field__input:invalid {
  box-shadow: none;
}
.mdc-text-field__input::placeholder {
  opacity: 0;
}
.mdc-text-field__input::-moz-placeholder {
  opacity: 0;
}
.mdc-text-field__input::-webkit-input-placeholder {
  opacity: 0;
}
.mdc-text-field__input:-ms-input-placeholder {
  opacity: 0;
}
.mdc-text-field--no-label .mdc-text-field__input::placeholder, .mdc-text-field--focused .mdc-text-field__input::placeholder {
  opacity: 1;
}
.mdc-text-field--no-label .mdc-text-field__input::-moz-placeholder, .mdc-text-field--focused .mdc-text-field__input::-moz-placeholder {
  opacity: 1;
}
.mdc-text-field--no-label .mdc-text-field__input::-webkit-input-placeholder, .mdc-text-field--focused .mdc-text-field__input::-webkit-input-placeholder {
  opacity: 1;
}
.mdc-text-field--no-label .mdc-text-field__input:-ms-input-placeholder, .mdc-text-field--focused .mdc-text-field__input:-ms-input-placeholder {
  opacity: 1;
}
.mdc-text-field--disabled:not(.mdc-text-field--no-label) .mdc-text-field__input.mat-mdc-input-disabled-interactive::placeholder {
  opacity: 0;
}
.mdc-text-field--disabled:not(.mdc-text-field--no-label) .mdc-text-field__input.mat-mdc-input-disabled-interactive::-moz-placeholder {
  opacity: 0;
}
.mdc-text-field--disabled:not(.mdc-text-field--no-label) .mdc-text-field__input.mat-mdc-input-disabled-interactive::-webkit-input-placeholder {
  opacity: 0;
}
.mdc-text-field--disabled:not(.mdc-text-field--no-label) .mdc-text-field__input.mat-mdc-input-disabled-interactive:-ms-input-placeholder {
  opacity: 0;
}
.mdc-text-field--outlined .mdc-text-field__input, .mdc-text-field--filled.mdc-text-field--no-label .mdc-text-field__input {
  height: 100%;
}
.mdc-text-field--outlined .mdc-text-field__input {
  display: flex;
  border: none !important;
  background-color: transparent;
}
.mdc-text-field--disabled .mdc-text-field__input {
  pointer-events: auto;
}
.mdc-text-field--filled:not(.mdc-text-field--disabled) .mdc-text-field__input {
  color: var(--mat-form-field-filled-input-text-color, var(--mat-sys-on-surface));
  caret-color: var(--mat-form-field-filled-caret-color, var(--mat-sys-primary));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled) .mdc-text-field__input::placeholder {
  color: var(--mat-form-field-filled-input-text-placeholder-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled) .mdc-text-field__input::-moz-placeholder {
  color: var(--mat-form-field-filled-input-text-placeholder-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled) .mdc-text-field__input::-webkit-input-placeholder {
  color: var(--mat-form-field-filled-input-text-placeholder-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled) .mdc-text-field__input:-ms-input-placeholder {
  color: var(--mat-form-field-filled-input-text-placeholder-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled) .mdc-text-field__input {
  color: var(--mat-form-field-outlined-input-text-color, var(--mat-sys-on-surface));
  caret-color: var(--mat-form-field-outlined-caret-color, var(--mat-sys-primary));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled) .mdc-text-field__input::placeholder {
  color: var(--mat-form-field-outlined-input-text-placeholder-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled) .mdc-text-field__input::-moz-placeholder {
  color: var(--mat-form-field-outlined-input-text-placeholder-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled) .mdc-text-field__input::-webkit-input-placeholder {
  color: var(--mat-form-field-outlined-input-text-placeholder-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled) .mdc-text-field__input:-ms-input-placeholder {
  color: var(--mat-form-field-outlined-input-text-placeholder-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--filled.mdc-text-field--invalid:not(.mdc-text-field--disabled) .mdc-text-field__input {
  caret-color: var(--mat-form-field-filled-error-caret-color, var(--mat-sys-error));
}
.mdc-text-field--outlined.mdc-text-field--invalid:not(.mdc-text-field--disabled) .mdc-text-field__input {
  caret-color: var(--mat-form-field-outlined-error-caret-color, var(--mat-sys-error));
}
.mdc-text-field--filled.mdc-text-field--disabled .mdc-text-field__input {
  color: var(--mat-form-field-filled-disabled-input-text-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mdc-text-field--outlined.mdc-text-field--disabled .mdc-text-field__input {
  color: var(--mat-form-field-outlined-disabled-input-text-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
@media (forced-colors: active) {
  .mdc-text-field--disabled .mdc-text-field__input {
    background-color: Window;
  }
}

.mdc-text-field--filled {
  height: 56px;
  border-bottom-right-radius: 0;
  border-bottom-left-radius: 0;
  border-top-left-radius: var(--mat-form-field-filled-container-shape, var(--mat-sys-corner-extra-small));
  border-top-right-radius: var(--mat-form-field-filled-container-shape, var(--mat-sys-corner-extra-small));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled) {
  background-color: var(--mat-form-field-filled-container-color, var(--mat-sys-surface-variant));
}
.mdc-text-field--filled.mdc-text-field--disabled {
  background-color: var(--mat-form-field-filled-disabled-container-color, color-mix(in srgb, var(--mat-sys-on-surface) 4%, transparent));
}

.mdc-text-field--outlined {
  height: 56px;
  overflow: visible;
  padding-right: max(16px, var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small)));
  padding-left: max(16px, var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small)) + 4px);
}
[dir=rtl] .mdc-text-field--outlined {
  padding-right: max(16px, var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small)) + 4px);
  padding-left: max(16px, var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small)));
}

.mdc-floating-label {
  position: absolute;
  left: 0;
  transform-origin: left top;
  line-height: 1.15rem;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: text;
  overflow: hidden;
  will-change: transform;
}
[dir=rtl] .mdc-floating-label {
  right: 0;
  left: auto;
  transform-origin: right top;
  text-align: right;
}
.mdc-text-field .mdc-floating-label {
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}
.mdc-notched-outline .mdc-floating-label {
  display: inline-block;
  position: relative;
  max-width: 100%;
}
.mdc-text-field--outlined .mdc-floating-label {
  left: 4px;
  right: auto;
}
[dir=rtl] .mdc-text-field--outlined .mdc-floating-label {
  left: auto;
  right: 4px;
}
.mdc-text-field--filled .mdc-floating-label {
  left: 16px;
  right: auto;
}
[dir=rtl] .mdc-text-field--filled .mdc-floating-label {
  left: auto;
  right: 16px;
}
.mdc-text-field--disabled .mdc-floating-label {
  cursor: default;
}
@media (forced-colors: active) {
  .mdc-text-field--disabled .mdc-floating-label {
    z-index: 1;
  }
}
.mdc-text-field--filled.mdc-text-field--no-label .mdc-floating-label {
  display: none;
}
.mdc-text-field--filled:not(.mdc-text-field--disabled) .mdc-floating-label {
  color: var(--mat-form-field-filled-label-text-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled).mdc-text-field--focused .mdc-floating-label {
  color: var(--mat-form-field-filled-focus-label-text-color, var(--mat-sys-primary));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled):not(.mdc-text-field--focused):hover .mdc-floating-label {
  color: var(--mat-form-field-filled-hover-label-text-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--filled.mdc-text-field--disabled .mdc-floating-label {
  color: var(--mat-form-field-filled-disabled-label-text-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled).mdc-text-field--invalid .mdc-floating-label {
  color: var(--mat-form-field-filled-error-label-text-color, var(--mat-sys-error));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled).mdc-text-field--invalid.mdc-text-field--focused .mdc-floating-label {
  color: var(--mat-form-field-filled-error-focus-label-text-color, var(--mat-sys-error));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled).mdc-text-field--invalid:not(.mdc-text-field--disabled):hover .mdc-floating-label {
  color: var(--mat-form-field-filled-error-hover-label-text-color, var(--mat-sys-on-error-container));
}
.mdc-text-field--filled .mdc-floating-label {
  font-family: var(--mat-form-field-filled-label-text-font, var(--mat-sys-body-large-font));
  font-size: var(--mat-form-field-filled-label-text-size, var(--mat-sys-body-large-size));
  font-weight: var(--mat-form-field-filled-label-text-weight, var(--mat-sys-body-large-weight));
  letter-spacing: var(--mat-form-field-filled-label-text-tracking, var(--mat-sys-body-large-tracking));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled) .mdc-floating-label {
  color: var(--mat-form-field-outlined-label-text-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled).mdc-text-field--focused .mdc-floating-label {
  color: var(--mat-form-field-outlined-focus-label-text-color, var(--mat-sys-primary));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled):not(.mdc-text-field--focused):hover .mdc-floating-label {
  color: var(--mat-form-field-outlined-hover-label-text-color, var(--mat-sys-on-surface));
}
.mdc-text-field--outlined.mdc-text-field--disabled .mdc-floating-label {
  color: var(--mat-form-field-outlined-disabled-label-text-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled).mdc-text-field--invalid .mdc-floating-label {
  color: var(--mat-form-field-outlined-error-label-text-color, var(--mat-sys-error));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled).mdc-text-field--invalid.mdc-text-field--focused .mdc-floating-label {
  color: var(--mat-form-field-outlined-error-focus-label-text-color, var(--mat-sys-error));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled).mdc-text-field--invalid:not(.mdc-text-field--disabled):hover .mdc-floating-label {
  color: var(--mat-form-field-outlined-error-hover-label-text-color, var(--mat-sys-on-error-container));
}
.mdc-text-field--outlined .mdc-floating-label {
  font-family: var(--mat-form-field-outlined-label-text-font, var(--mat-sys-body-large-font));
  font-size: var(--mat-form-field-outlined-label-text-size, var(--mat-sys-body-large-size));
  font-weight: var(--mat-form-field-outlined-label-text-weight, var(--mat-sys-body-large-weight));
  letter-spacing: var(--mat-form-field-outlined-label-text-tracking, var(--mat-sys-body-large-tracking));
}

.mdc-floating-label--float-above {
  cursor: auto;
  transform: translateY(-106%) scale(0.75);
}
.mdc-text-field--filled .mdc-floating-label--float-above {
  transform: translateY(-106%) scale(0.75);
}
.mdc-text-field--outlined .mdc-floating-label--float-above {
  transform: translateY(-37.25px) scale(1);
  font-size: 0.75rem;
}
.mdc-notched-outline .mdc-floating-label--float-above {
  text-overflow: clip;
}
.mdc-notched-outline--upgraded .mdc-floating-label--float-above {
  max-width: 133.3333333333%;
}
.mdc-text-field--outlined.mdc-notched-outline--upgraded .mdc-floating-label--float-above, .mdc-text-field--outlined .mdc-notched-outline--upgraded .mdc-floating-label--float-above {
  transform: translateY(-34.75px) scale(0.75);
}
.mdc-text-field--outlined.mdc-notched-outline--upgraded .mdc-floating-label--float-above, .mdc-text-field--outlined .mdc-notched-outline--upgraded .mdc-floating-label--float-above {
  font-size: 1rem;
}

.mdc-floating-label--required:not(.mdc-floating-label--hide-required-marker)::after {
  margin-left: 1px;
  margin-right: 0;
  content: "*";
}
[dir=rtl] .mdc-floating-label--required:not(.mdc-floating-label--hide-required-marker)::after {
  margin-left: 0;
  margin-right: 1px;
}

.mdc-notched-outline {
  display: flex;
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  height: 100%;
  text-align: left;
  pointer-events: none;
}
[dir=rtl] .mdc-notched-outline {
  text-align: right;
}
.mdc-text-field--outlined .mdc-notched-outline {
  z-index: 1;
}

.mat-mdc-notch-piece {
  box-sizing: border-box;
  height: 100%;
  pointer-events: none;
  border: none;
  border-top: 1px solid;
  border-bottom: 1px solid;
}
.mdc-text-field--focused .mat-mdc-notch-piece {
  border-width: 2px;
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled) .mat-mdc-notch-piece {
  border-color: var(--mat-form-field-outlined-outline-color, var(--mat-sys-outline));
  border-width: var(--mat-form-field-outlined-outline-width, 1px);
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled):not(.mdc-text-field--focused):hover .mat-mdc-notch-piece {
  border-color: var(--mat-form-field-outlined-hover-outline-color, var(--mat-sys-on-surface));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled).mdc-text-field--focused .mat-mdc-notch-piece {
  border-color: var(--mat-form-field-outlined-focus-outline-color, var(--mat-sys-primary));
}
.mdc-text-field--outlined.mdc-text-field--disabled .mat-mdc-notch-piece {
  border-color: var(--mat-form-field-outlined-disabled-outline-color, color-mix(in srgb, var(--mat-sys-on-surface) 12%, transparent));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled).mdc-text-field--invalid .mat-mdc-notch-piece {
  border-color: var(--mat-form-field-outlined-error-outline-color, var(--mat-sys-error));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled).mdc-text-field--invalid:not(.mdc-text-field--focused):hover .mdc-notched-outline .mat-mdc-notch-piece {
  border-color: var(--mat-form-field-outlined-error-hover-outline-color, var(--mat-sys-on-error-container));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled).mdc-text-field--invalid.mdc-text-field--focused .mat-mdc-notch-piece {
  border-color: var(--mat-form-field-outlined-error-focus-outline-color, var(--mat-sys-error));
}
.mdc-text-field--outlined:not(.mdc-text-field--disabled).mdc-text-field--focused .mdc-notched-outline .mat-mdc-notch-piece {
  border-width: var(--mat-form-field-outlined-focus-outline-width, 2px);
}

.mdc-notched-outline__leading {
  border-left: 1px solid;
  border-right: none;
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
  border-top-left-radius: var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small));
  border-bottom-left-radius: var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small));
}
.mdc-text-field--outlined .mdc-notched-outline .mdc-notched-outline__leading {
  width: max(12px, var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small)));
}
[dir=rtl] .mdc-notched-outline__leading {
  border-left: none;
  border-right: 1px solid;
  border-bottom-left-radius: 0;
  border-top-left-radius: 0;
  border-top-right-radius: var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small));
  border-bottom-right-radius: var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small));
}

.mdc-notched-outline__trailing {
  flex-grow: 1;
  border-left: none;
  border-right: 1px solid;
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
  border-top-right-radius: var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small));
  border-bottom-right-radius: var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small));
}
[dir=rtl] .mdc-notched-outline__trailing {
  border-left: 1px solid;
  border-right: none;
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
  border-top-left-radius: var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small));
  border-bottom-left-radius: var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small));
}

.mdc-notched-outline__notch {
  flex: 0 0 auto;
  width: auto;
}
.mdc-text-field--outlined .mdc-notched-outline .mdc-notched-outline__notch {
  max-width: min(var(--mat-form-field-notch-max-width, 100%), calc(100% - max(12px, var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small))) * 2));
}
.mdc-text-field--outlined .mdc-notched-outline--notched .mdc-notched-outline__notch {
  max-width: min(100%, calc(100% - max(12px, var(--mat-form-field-outlined-container-shape, var(--mat-sys-corner-extra-small))) * 2));
}
.mdc-text-field--outlined .mdc-notched-outline--notched .mdc-notched-outline__notch {
  padding-top: 1px;
}
.mdc-text-field--focused.mdc-text-field--outlined .mdc-notched-outline--notched .mdc-notched-outline__notch {
  padding-top: 2px;
}
.mdc-notched-outline--notched .mdc-notched-outline__notch {
  padding-left: 0;
  padding-right: 8px;
  border-top: none;
}
[dir=rtl] .mdc-notched-outline--notched .mdc-notched-outline__notch {
  padding-left: 8px;
  padding-right: 0;
}
.mdc-notched-outline--no-label .mdc-notched-outline__notch {
  display: none;
}

.mdc-line-ripple::before, .mdc-line-ripple::after {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  border-bottom-style: solid;
  content: "";
}
.mdc-line-ripple::before {
  z-index: 1;
  border-bottom-width: var(--mat-form-field-filled-active-indicator-height, 1px);
}
.mdc-text-field--filled:not(.mdc-text-field--disabled) .mdc-line-ripple::before {
  border-bottom-color: var(--mat-form-field-filled-active-indicator-color, var(--mat-sys-on-surface-variant));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled):not(.mdc-text-field--focused):hover .mdc-line-ripple::before {
  border-bottom-color: var(--mat-form-field-filled-hover-active-indicator-color, var(--mat-sys-on-surface));
}
.mdc-text-field--filled.mdc-text-field--disabled .mdc-line-ripple::before {
  border-bottom-color: var(--mat-form-field-filled-disabled-active-indicator-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled).mdc-text-field--invalid .mdc-line-ripple::before {
  border-bottom-color: var(--mat-form-field-filled-error-active-indicator-color, var(--mat-sys-error));
}
.mdc-text-field--filled:not(.mdc-text-field--disabled).mdc-text-field--invalid:not(.mdc-text-field--focused):hover .mdc-line-ripple::before {
  border-bottom-color: var(--mat-form-field-filled-error-hover-active-indicator-color, var(--mat-sys-on-error-container));
}
.mdc-line-ripple::after {
  transform: scaleX(0);
  opacity: 0;
  z-index: 2;
}
.mdc-text-field--filled .mdc-line-ripple::after {
  border-bottom-width: var(--mat-form-field-filled-focus-active-indicator-height, 2px);
}
.mdc-text-field--filled:not(.mdc-text-field--disabled) .mdc-line-ripple::after {
  border-bottom-color: var(--mat-form-field-filled-focus-active-indicator-color, var(--mat-sys-primary));
}
.mdc-text-field--filled.mdc-text-field--invalid:not(.mdc-text-field--disabled) .mdc-line-ripple::after {
  border-bottom-color: var(--mat-form-field-filled-error-focus-active-indicator-color, var(--mat-sys-error));
}

.mdc-line-ripple--active::after {
  transform: scaleX(1);
  opacity: 1;
}

.mdc-line-ripple--deactivating::after {
  opacity: 0;
}

.mdc-text-field--disabled {
  pointer-events: none;
}

.mat-mdc-form-field-textarea-control {
  vertical-align: middle;
  resize: vertical;
  box-sizing: border-box;
  height: auto;
  margin: 0;
  padding: 0;
  border: none;
  overflow: auto;
}

.mat-mdc-form-field-input-control.mat-mdc-form-field-input-control {
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  font: inherit;
  letter-spacing: inherit;
  text-decoration: inherit;
  text-transform: inherit;
  border: none;
}

.mat-mdc-form-field .mat-mdc-floating-label.mdc-floating-label {
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  line-height: normal;
  pointer-events: all;
  will-change: auto;
}

.mat-mdc-form-field:not(.mat-form-field-disabled) .mat-mdc-floating-label.mdc-floating-label {
  cursor: inherit;
}

.mdc-text-field--no-label:not(.mdc-text-field--textarea) .mat-mdc-form-field-input-control.mdc-text-field__input,
.mat-mdc-text-field-wrapper .mat-mdc-form-field-input-control {
  height: auto;
}

.mat-mdc-text-field-wrapper .mat-mdc-form-field-input-control.mdc-text-field__input[type=color] {
  height: 23px;
}

.mat-mdc-text-field-wrapper {
  height: auto;
  flex: auto;
  will-change: auto;
}

.mat-mdc-form-field-has-icon-prefix .mat-mdc-text-field-wrapper {
  padding-left: 0;
  --mat-mdc-form-field-label-offset-x: -16px;
}

.mat-mdc-form-field-has-icon-suffix .mat-mdc-text-field-wrapper {
  padding-right: 0;
}

[dir=rtl] .mat-mdc-text-field-wrapper {
  padding-left: 16px;
  padding-right: 16px;
}
[dir=rtl] .mat-mdc-form-field-has-icon-suffix .mat-mdc-text-field-wrapper {
  padding-left: 0;
}
[dir=rtl] .mat-mdc-form-field-has-icon-prefix .mat-mdc-text-field-wrapper {
  padding-right: 0;
}

.mat-form-field-disabled .mdc-text-field__input::placeholder {
  color: var(--mat-form-field-disabled-input-text-placeholder-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mat-form-field-disabled .mdc-text-field__input::-moz-placeholder {
  color: var(--mat-form-field-disabled-input-text-placeholder-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mat-form-field-disabled .mdc-text-field__input::-webkit-input-placeholder {
  color: var(--mat-form-field-disabled-input-text-placeholder-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mat-form-field-disabled .mdc-text-field__input:-ms-input-placeholder {
  color: var(--mat-form-field-disabled-input-text-placeholder-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}

.mat-mdc-form-field-label-always-float .mdc-text-field__input::placeholder {
  transition-delay: 40ms;
  transition-duration: 110ms;
  opacity: 1;
}

.mat-mdc-text-field-wrapper .mat-mdc-form-field-infix .mat-mdc-floating-label {
  left: auto;
  right: auto;
}

.mat-mdc-text-field-wrapper.mdc-text-field--outlined .mdc-text-field__input {
  display: inline-block;
}

.mat-mdc-form-field .mat-mdc-text-field-wrapper.mdc-text-field .mdc-notched-outline__notch {
  padding-top: 0;
}

.mat-mdc-form-field.mat-mdc-form-field.mat-mdc-form-field.mat-mdc-form-field.mat-mdc-form-field.mat-mdc-form-field .mdc-notched-outline__notch {
  border-left: 1px solid transparent;
}

[dir=rtl] .mat-mdc-form-field.mat-mdc-form-field.mat-mdc-form-field.mat-mdc-form-field.mat-mdc-form-field.mat-mdc-form-field .mdc-notched-outline__notch {
  border-left: none;
  border-right: 1px solid transparent;
}

.mat-mdc-form-field-infix {
  min-height: var(--mat-form-field-container-height, 56px);
  padding-top: var(--mat-form-field-filled-with-label-container-padding-top, 24px);
  padding-bottom: var(--mat-form-field-filled-with-label-container-padding-bottom, 8px);
}
.mdc-text-field--outlined .mat-mdc-form-field-infix, .mdc-text-field--no-label .mat-mdc-form-field-infix {
  padding-top: var(--mat-form-field-container-vertical-padding, 16px);
  padding-bottom: var(--mat-form-field-container-vertical-padding, 16px);
}

.mat-mdc-text-field-wrapper .mat-mdc-form-field-flex .mat-mdc-floating-label {
  top: calc(var(--mat-form-field-container-height, 56px) / 2);
}

.mdc-text-field--filled .mat-mdc-floating-label {
  display: var(--mat-form-field-filled-label-display, block);
}

.mat-mdc-text-field-wrapper.mdc-text-field--outlined .mdc-notched-outline--upgraded .mdc-floating-label--float-above {
  --mat-mdc-form-field-label-transform: translateY(calc(calc(6.75px + var(--mat-form-field-container-height, 56px) / 2) * -1))
    scale(var(--mat-mdc-form-field-floating-label-scale, 0.75));
  transform: var(--mat-mdc-form-field-label-transform);
}

@keyframes _mat-form-field-subscript-animation {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.mat-mdc-form-field-subscript-wrapper {
  box-sizing: border-box;
  width: 100%;
  position: relative;
}

.mat-mdc-form-field-hint-wrapper,
.mat-mdc-form-field-error-wrapper {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 0 16px;
  opacity: 1;
  transform: translateY(0);
  animation: _mat-form-field-subscript-animation 0ms cubic-bezier(0.55, 0, 0.55, 0.2);
}

.mat-mdc-form-field-subscript-dynamic-size .mat-mdc-form-field-hint-wrapper,
.mat-mdc-form-field-subscript-dynamic-size .mat-mdc-form-field-error-wrapper {
  position: static;
}

.mat-mdc-form-field-bottom-align::before {
  content: "";
  display: inline-block;
  height: 16px;
}

.mat-mdc-form-field-bottom-align.mat-mdc-form-field-subscript-dynamic-size::before {
  content: unset;
}

.mat-mdc-form-field-hint-end {
  order: 1;
}

.mat-mdc-form-field-hint-wrapper {
  display: flex;
}

.mat-mdc-form-field-hint-spacer {
  flex: 1 0 1em;
}

.mat-mdc-form-field-error {
  display: block;
  color: var(--mat-form-field-error-text-color, var(--mat-sys-error));
}

.mat-mdc-form-field-subscript-wrapper,
.mat-mdc-form-field-bottom-align::before {
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  font-family: var(--mat-form-field-subscript-text-font, var(--mat-sys-body-small-font));
  line-height: var(--mat-form-field-subscript-text-line-height, var(--mat-sys-body-small-line-height));
  font-size: var(--mat-form-field-subscript-text-size, var(--mat-sys-body-small-size));
  letter-spacing: var(--mat-form-field-subscript-text-tracking, var(--mat-sys-body-small-tracking));
  font-weight: var(--mat-form-field-subscript-text-weight, var(--mat-sys-body-small-weight));
}

.mat-mdc-form-field-focus-overlay {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  opacity: 0;
  pointer-events: none;
  background-color: var(--mat-form-field-state-layer-color, var(--mat-sys-on-surface));
}
.mat-mdc-text-field-wrapper:hover .mat-mdc-form-field-focus-overlay {
  opacity: var(--mat-form-field-hover-state-layer-opacity, var(--mat-sys-hover-state-layer-opacity));
}
.mat-mdc-form-field.mat-focused .mat-mdc-form-field-focus-overlay {
  opacity: var(--mat-form-field-focus-state-layer-opacity, 0);
}

select.mat-mdc-form-field-input-control {
  -moz-appearance: none;
  -webkit-appearance: none;
  background-color: transparent;
  display: inline-flex;
  box-sizing: border-box;
}
select.mat-mdc-form-field-input-control:not(:disabled) {
  cursor: pointer;
}
select.mat-mdc-form-field-input-control:not(.mat-mdc-native-select-inline) option {
  color: var(--mat-form-field-select-option-text-color, var(--mat-sys-neutral10));
}
select.mat-mdc-form-field-input-control:not(.mat-mdc-native-select-inline) option:disabled {
  color: var(--mat-form-field-select-disabled-option-text-color, color-mix(in srgb, var(--mat-sys-neutral10) 38%, transparent));
}

.mat-mdc-form-field-type-mat-native-select .mat-mdc-form-field-infix::after {
  content: "";
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 5px solid;
  position: absolute;
  right: 0;
  top: 50%;
  margin-top: -2.5px;
  pointer-events: none;
  color: var(--mat-form-field-enabled-select-arrow-color, var(--mat-sys-on-surface-variant));
}
[dir=rtl] .mat-mdc-form-field-type-mat-native-select .mat-mdc-form-field-infix::after {
  right: auto;
  left: 0;
}
.mat-mdc-form-field-type-mat-native-select.mat-focused .mat-mdc-form-field-infix::after {
  color: var(--mat-form-field-focus-select-arrow-color, var(--mat-sys-primary));
}
.mat-mdc-form-field-type-mat-native-select.mat-form-field-disabled .mat-mdc-form-field-infix::after {
  color: var(--mat-form-field-disabled-select-arrow-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mat-mdc-form-field-type-mat-native-select .mat-mdc-form-field-input-control {
  padding-right: 15px;
}
[dir=rtl] .mat-mdc-form-field-type-mat-native-select .mat-mdc-form-field-input-control {
  padding-right: 0;
  padding-left: 15px;
}

@media (forced-colors: active) {
  .mat-form-field-appearance-fill .mat-mdc-text-field-wrapper {
    outline: solid 1px;
  }
}
@media (forced-colors: active) {
  .mat-form-field-appearance-fill.mat-form-field-disabled .mat-mdc-text-field-wrapper {
    outline-color: GrayText;
  }
}

@media (forced-colors: active) {
  .mat-form-field-appearance-fill.mat-focused .mat-mdc-text-field-wrapper {
    outline: dashed 3px;
  }
}

@media (forced-colors: active) {
  .mat-mdc-form-field.mat-focused .mdc-notched-outline {
    border: dashed 3px;
  }
}

.mat-mdc-form-field-input-control[type=date], .mat-mdc-form-field-input-control[type=datetime], .mat-mdc-form-field-input-control[type=datetime-local], .mat-mdc-form-field-input-control[type=month], .mat-mdc-form-field-input-control[type=week], .mat-mdc-form-field-input-control[type=time] {
  line-height: 1;
}
.mat-mdc-form-field-input-control::-webkit-datetime-edit {
  line-height: 1;
  padding: 0;
  margin-bottom: -2px;
}

.mat-mdc-form-field {
  --mat-mdc-form-field-floating-label-scale: 0.75;
  display: inline-flex;
  flex-direction: column;
  min-width: 0;
  text-align: left;
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  font-family: var(--mat-form-field-container-text-font, var(--mat-sys-body-large-font));
  line-height: var(--mat-form-field-container-text-line-height, var(--mat-sys-body-large-line-height));
  font-size: var(--mat-form-field-container-text-size, var(--mat-sys-body-large-size));
  letter-spacing: var(--mat-form-field-container-text-tracking, var(--mat-sys-body-large-tracking));
  font-weight: var(--mat-form-field-container-text-weight, var(--mat-sys-body-large-weight));
}
.mat-mdc-form-field .mdc-text-field--outlined .mdc-floating-label--float-above {
  font-size: calc(var(--mat-form-field-outlined-label-text-populated-size) * var(--mat-mdc-form-field-floating-label-scale));
}
.mat-mdc-form-field .mdc-text-field--outlined .mdc-notched-outline--upgraded .mdc-floating-label--float-above {
  font-size: var(--mat-form-field-outlined-label-text-populated-size);
}
[dir=rtl] .mat-mdc-form-field {
  text-align: right;
}

.mat-mdc-form-field-flex {
  display: inline-flex;
  align-items: baseline;
  box-sizing: border-box;
  width: 100%;
}

.mat-mdc-text-field-wrapper {
  width: 100%;
  z-index: 0;
}

.mat-mdc-form-field-icon-prefix,
.mat-mdc-form-field-icon-suffix {
  align-self: center;
  line-height: 0;
  pointer-events: auto;
  position: relative;
  z-index: 1;
}
.mat-mdc-form-field-icon-prefix > .mat-icon,
.mat-mdc-form-field-icon-suffix > .mat-icon {
  padding: 0 12px;
  box-sizing: content-box;
}

.mat-mdc-form-field-icon-prefix {
  color: var(--mat-form-field-leading-icon-color, var(--mat-sys-on-surface-variant));
}
.mat-form-field-disabled .mat-mdc-form-field-icon-prefix {
  color: var(--mat-form-field-disabled-leading-icon-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}

.mat-mdc-form-field-icon-suffix {
  color: var(--mat-form-field-trailing-icon-color, var(--mat-sys-on-surface-variant));
}
.mat-form-field-disabled .mat-mdc-form-field-icon-suffix {
  color: var(--mat-form-field-disabled-trailing-icon-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mat-form-field-invalid .mat-mdc-form-field-icon-suffix {
  color: var(--mat-form-field-error-trailing-icon-color, var(--mat-sys-error));
}
.mat-form-field-invalid:not(.mat-focused):not(.mat-form-field-disabled) .mat-mdc-text-field-wrapper:hover .mat-mdc-form-field-icon-suffix {
  color: var(--mat-form-field-error-hover-trailing-icon-color, var(--mat-sys-on-error-container));
}
.mat-form-field-invalid.mat-focused .mat-mdc-text-field-wrapper .mat-mdc-form-field-icon-suffix {
  color: var(--mat-form-field-error-focus-trailing-icon-color, var(--mat-sys-error));
}

.mat-mdc-form-field-icon-prefix,
[dir=rtl] .mat-mdc-form-field-icon-suffix {
  padding: 0 4px 0 0;
}

.mat-mdc-form-field-icon-suffix,
[dir=rtl] .mat-mdc-form-field-icon-prefix {
  padding: 0 0 0 4px;
}

.mat-mdc-form-field-subscript-wrapper .mat-icon,
.mat-mdc-form-field label .mat-icon {
  width: 1em;
  height: 1em;
  font-size: inherit;
}

.mat-mdc-form-field-infix {
  flex: auto;
  min-width: 0;
  width: 180px;
  position: relative;
  box-sizing: border-box;
}
.mat-mdc-form-field-infix:has(textarea[cols]) {
  width: auto;
}

.mat-mdc-form-field .mdc-notched-outline__notch {
  margin-left: -1px;
  -webkit-clip-path: inset(-9em -999em -9em 1px);
  clip-path: inset(-9em -999em -9em 1px);
}
[dir=rtl] .mat-mdc-form-field .mdc-notched-outline__notch {
  margin-left: 0;
  margin-right: -1px;
  -webkit-clip-path: inset(-9em 1px -9em -999em);
  clip-path: inset(-9em 1px -9em -999em);
}

.mat-mdc-form-field.mat-form-field-animations-enabled .mdc-floating-label {
  transition: transform 150ms cubic-bezier(0.4, 0, 0.2, 1), color 150ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mat-mdc-form-field.mat-form-field-animations-enabled .mdc-text-field__input {
  transition: opacity 150ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mat-mdc-form-field.mat-form-field-animations-enabled .mdc-text-field__input::placeholder {
  transition: opacity 67ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mat-mdc-form-field.mat-form-field-animations-enabled .mdc-text-field__input::-moz-placeholder {
  transition: opacity 67ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mat-mdc-form-field.mat-form-field-animations-enabled .mdc-text-field__input::-webkit-input-placeholder {
  transition: opacity 67ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mat-mdc-form-field.mat-form-field-animations-enabled .mdc-text-field__input:-ms-input-placeholder {
  transition: opacity 67ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mat-mdc-form-field.mat-form-field-animations-enabled.mdc-text-field--no-label .mdc-text-field__input::placeholder, .mat-mdc-form-field.mat-form-field-animations-enabled.mdc-text-field--focused .mdc-text-field__input::placeholder {
  transition-delay: 40ms;
  transition-duration: 110ms;
}
.mat-mdc-form-field.mat-form-field-animations-enabled.mdc-text-field--no-label .mdc-text-field__input::-moz-placeholder, .mat-mdc-form-field.mat-form-field-animations-enabled.mdc-text-field--focused .mdc-text-field__input::-moz-placeholder {
  transition-delay: 40ms;
  transition-duration: 110ms;
}
.mat-mdc-form-field.mat-form-field-animations-enabled.mdc-text-field--no-label .mdc-text-field__input::-webkit-input-placeholder, .mat-mdc-form-field.mat-form-field-animations-enabled.mdc-text-field--focused .mdc-text-field__input::-webkit-input-placeholder {
  transition-delay: 40ms;
  transition-duration: 110ms;
}
.mat-mdc-form-field.mat-form-field-animations-enabled.mdc-text-field--no-label .mdc-text-field__input:-ms-input-placeholder, .mat-mdc-form-field.mat-form-field-animations-enabled.mdc-text-field--focused .mdc-text-field__input:-ms-input-placeholder {
  transition-delay: 40ms;
  transition-duration: 110ms;
}
.mat-mdc-form-field.mat-form-field-animations-enabled .mdc-text-field--filled:not(.mdc-ripple-upgraded):focus .mdc-text-field__ripple::before {
  transition-duration: 75ms;
}
.mat-mdc-form-field.mat-form-field-animations-enabled .mdc-line-ripple::after {
  transition: transform 180ms cubic-bezier(0.4, 0, 0.2, 1), opacity 180ms cubic-bezier(0.4, 0, 0.2, 1);
}
.mat-mdc-form-field.mat-form-field-animations-enabled .mat-mdc-form-field-hint-wrapper,
.mat-mdc-form-field.mat-form-field-animations-enabled .mat-mdc-form-field-error-wrapper {
  animation-duration: 300ms;
}

.mdc-notched-outline .mdc-floating-label {
  max-width: calc(100% + 1px);
}

.mdc-notched-outline--upgraded .mdc-floating-label--float-above {
  max-width: calc(133.3333333333% + 1px);
}
`],encapsulation:2,changeDetection:0})}return i})();var Li=(()=>{class i{isErrorState(e,t){return!!(e&&e.invalid&&(e.touched||t&&t.submitted))}static \u0275fac=function(t){return new(t||i)};static \u0275prov=V({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})();var Dt=class{_defaultMatcher;ngControl;_parentFormGroup;_parentForm;_stateChanges;errorState=!1;matcher;constructor(s,e,t,n,a){this._defaultMatcher=s,this.ngControl=e,this._parentFormGroup=t,this._parentForm=n,this._stateChanges=a}updateErrorState(){let s=this.errorState,e=this._parentFormGroup||this._parentForm,t=this.matcher||this._defaultMatcher,n=this.ngControl?this.ngControl.control:null,a=t?.isErrorState(n,e)??!1;a!==s&&(this.errorState=a,this._stateChanges.next())}};var Fi=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[ti,Pi,W]})}return i})();var bo=["trigger"],_o=["panel"],go=[[["mat-select-trigger"]],"*"],vo=["mat-select-trigger","*"];function yo(i,s){if(i&1&&(h(0,"span",4),se(1),u()),i&2){let e=x();c(),we(e.placeholder)}}function xo(i,s){i&1&&k(0)}function ko(i,s){if(i&1&&(h(0,"span",11),se(1),u()),i&2){let e=x(2);c(),we(e.triggerValue)}}function Co(i,s){if(i&1&&(h(0,"span",5),O(1,xo,1,0)(2,ko,2,1,"span",11),u()),i&2){let e=x();c(),P(e.customTrigger?1:2)}}function wo(i,s){if(i&1){let e=Ne();h(0,"div",12,1),M("keydown",function(n){ae(e);let a=x();return oe(a._handleKeydown(n))}),k(2,1),u()}if(i&2){let e=x();H(e.panelClass),g("mat-select-panel-animations-enabled",!e._animationsDisabled)("mat-primary",(e._parentFormField==null?null:e._parentFormField.color)==="primary")("mat-accent",(e._parentFormField==null?null:e._parentFormField.color)==="accent")("mat-warn",(e._parentFormField==null?null:e._parentFormField.color)==="warn")("mat-undefined",!(e._parentFormField!=null&&e._parentFormField.color)),T("id",e.id+"-panel")("aria-multiselectable",e.multiple)("aria-label",e.ariaLabel||null)("aria-labelledby",e._getPanelAriaLabelledby())}}var To=new w("mat-select-scroll-strategy",{providedIn:"root",factory:()=>{let i=r(re);return()=>Qe(i)}}),Mo=new w("MAT_SELECT_CONFIG"),Ai=new w("MatSelectTrigger"),tn=class{source;value;constructor(s,e){this.source=s,this.value=e}},nc=(()=>{class i{_viewportRuler=r(it);_changeDetectorRef=r(U);_elementRef=r(I);_dir=r(pe,{optional:!0});_idGenerator=r(q);_renderer=r(te);_parentFormField=r(en,{optional:!0});ngControl=r(qn,{self:!0,optional:!0});_liveAnnouncer=r(ni);_defaultOptions=r(Mo,{optional:!0});_animationsDisabled=K();_popoverLocation;_initialized=new _;_cleanupDetach;options;optionGroups;customTrigger;_positions=[{originX:"start",originY:"bottom",overlayX:"start",overlayY:"top"},{originX:"end",originY:"bottom",overlayX:"end",overlayY:"top"},{originX:"start",originY:"top",overlayX:"start",overlayY:"bottom",panelClass:"mat-mdc-select-panel-above"},{originX:"end",originY:"top",overlayX:"end",overlayY:"bottom",panelClass:"mat-mdc-select-panel-above"}];_scrollOptionIntoView(e){let t=this.options.toArray()[e];if(t){let n=this.panel.nativeElement,a=bi(e,this.options,this.optionGroups),o=t._getHostElement();e===0&&a===1?n.scrollTop=0:n.scrollTop=_i(o.offsetTop,o.offsetHeight,n.scrollTop,n.offsetHeight)}}_positioningSettled(){this._scrollOptionIntoView(this._keyManager.activeItemIndex||0)}_getChangeEvent(e){return new tn(this,e)}_scrollStrategyFactory=r(To);_panelOpen=!1;_compareWith=(e,t)=>e===t;_uid=this._idGenerator.getId("mat-select-");_triggerAriaLabelledBy=null;_previousControl;_destroy=new _;_errorStateTracker;stateChanges=new _;disableAutomaticLabeling=!0;userAriaDescribedBy;_selectionModel;_keyManager;_preferredOverlayOrigin;_overlayWidth;_onChange=()=>{};_onTouched=()=>{};_valueId=this._idGenerator.getId("mat-select-value-");_scrollStrategy;_overlayPanelClass=this._defaultOptions?.overlayPanelClass||"";get focused(){return this._focused||this._panelOpen}_focused=!1;controlType="mat-select";trigger;panel;_overlayDir;panelClass;disabled=!1;get disableRipple(){return this._disableRipple()}set disableRipple(e){this._disableRipple.set(e)}_disableRipple=Z(!1);tabIndex=0;get hideSingleSelectionIndicator(){return this._hideSingleSelectionIndicator}set hideSingleSelectionIndicator(e){this._hideSingleSelectionIndicator=e,this._syncParentProperties()}_hideSingleSelectionIndicator=this._defaultOptions?.hideSingleSelectionIndicator??!1;get placeholder(){return this._placeholder}set placeholder(e){this._placeholder=e,this.stateChanges.next()}_placeholder;get required(){return this._required??this.ngControl?.control?.hasValidator(Qn.required)??!1}set required(e){this._required=e,this.stateChanges.next()}_required;get multiple(){return this._multiple}set multiple(e){this._selectionModel,this._multiple=e}_multiple=!1;disableOptionCentering=this._defaultOptions?.disableOptionCentering??!1;get compareWith(){return this._compareWith}set compareWith(e){this._compareWith=e,this._selectionModel&&this._initializeSelection()}get value(){return this._value}set value(e){this._assignValue(e)&&this._onChange(e)}_value;ariaLabel="";ariaLabelledby;get errorStateMatcher(){return this._errorStateTracker.matcher}set errorStateMatcher(e){this._errorStateTracker.matcher=e}typeaheadDebounceInterval;sortComparator;get id(){return this._id}set id(e){this._id=e||this._uid,this.stateChanges.next()}_id;get errorState(){return this._errorStateTracker.errorState}set errorState(e){this._errorStateTracker.errorState=e}panelWidth=this._defaultOptions&&typeof this._defaultOptions.panelWidth<"u"?this._defaultOptions.panelWidth:"auto";canSelectNullableOptions=this._defaultOptions?.canSelectNullableOptions??!1;optionSelectionChanges=un(()=>{let e=this.options;return e?e.changes.pipe(ee(e),Ee(()=>N(...e.map(t=>t.onSelectionChange)))):this._initialized.pipe(Ee(()=>this.optionSelectionChanges))});openedChange=new p;_openedStream=this.openedChange.pipe(Q(e=>e),he(()=>{}));_closedStream=this.openedChange.pipe(Q(e=>!e),he(()=>{}));selectionChange=new p;valueChange=new p;constructor(){let e=r(Li),t=r(Kn,{optional:!0}),n=r(Xn,{optional:!0}),a=r(new $e("tabindex"),{optional:!0}),o=r(Yn,{optional:!0});this.ngControl&&(this.ngControl.valueAccessor=this),this._defaultOptions?.typeaheadDebounceInterval!=null&&(this.typeaheadDebounceInterval=this._defaultOptions.typeaheadDebounceInterval),this._errorStateTracker=new Dt(e,this.ngControl,n,t,this.stateChanges),this._scrollStrategy=this._scrollStrategyFactory(),this.tabIndex=a==null?0:parseInt(a)||0,this._popoverLocation=o?.usePopover===!1?null:"inline",this.id=this.id}ngOnInit(){this._selectionModel=new mi(this.multiple),this.stateChanges.next(),this._viewportRuler.change().pipe(y(this._destroy)).subscribe(()=>{this.panelOpen&&(this._overlayWidth=this._getOverlayWidth(this._preferredOverlayOrigin),this._changeDetectorRef.detectChanges())})}ngAfterContentInit(){this._initialized.next(),this._initialized.complete(),this._initKeyManager(),this._selectionModel.changed.pipe(y(this._destroy)).subscribe(e=>{e.added.forEach(t=>t.select()),e.removed.forEach(t=>t.deselect())}),this.options.changes.pipe(ee(null),y(this._destroy)).subscribe(()=>{this._resetOptions(),this._initializeSelection()})}ngDoCheck(){let e=this._getTriggerAriaLabelledby(),t=this.ngControl;if(e!==this._triggerAriaLabelledBy){let n=this._elementRef.nativeElement;this._triggerAriaLabelledBy=e,e?n.setAttribute("aria-labelledby",e):n.removeAttribute("aria-labelledby")}t&&(this._previousControl!==t.control&&(this._previousControl!==void 0&&t.disabled!==null&&t.disabled!==this.disabled&&(this.disabled=t.disabled),this._previousControl=t.control),this.updateErrorState())}ngOnChanges(e){(e.disabled||e.userAriaDescribedBy)&&this.stateChanges.next(),e.typeaheadDebounceInterval&&this._keyManager&&this._keyManager.withTypeAhead(this.typeaheadDebounceInterval),e.panelClass&&this.panelClass instanceof Set&&(this.panelClass=Array.from(this.panelClass))}ngOnDestroy(){this._cleanupDetach?.(),this._keyManager?.destroy(),this._destroy.next(),this._destroy.complete(),this.stateChanges.complete(),this._clearFromModal()}toggle(){this.panelOpen?this.close():this.open()}open(){this._canOpen()&&(this._parentFormField&&(this._preferredOverlayOrigin=this._parentFormField.getConnectedOverlayOrigin()),this._cleanupDetach?.(),this._overlayWidth=this._getOverlayWidth(this._preferredOverlayOrigin),this._applyModalPanelOwnership(),this._panelOpen=!0,this._overlayDir.positionChange.pipe(Ge(1)).subscribe(()=>{this._changeDetectorRef.detectChanges(),this._positioningSettled()}),this._overlayDir.attachOverlay(),this._keyManager.withHorizontalOrientation(null),this._highlightCorrectOption(),this._changeDetectorRef.markForCheck(),this.stateChanges.next(),Promise.resolve().then(()=>this.openedChange.emit(!0)))}_trackedModal=null;_applyModalPanelOwnership(){let e=this._elementRef.nativeElement.closest('body > .cdk-overlay-container [aria-modal="true"]');if(!e)return;let t=`${this.id}-panel`;this._trackedModal&&Wt(this._trackedModal,"aria-owns",t),oi(e,"aria-owns",t),this._trackedModal=e}_clearFromModal(){if(!this._trackedModal)return;let e=`${this.id}-panel`;Wt(this._trackedModal,"aria-owns",e),this._trackedModal=null}close(){this._panelOpen&&(this._panelOpen=!1,this._exitAndDetach(),this._keyManager.withHorizontalOrientation(this._isRtl()?"rtl":"ltr"),this._changeDetectorRef.markForCheck(),this._onTouched(),this.stateChanges.next(),Promise.resolve().then(()=>this.openedChange.emit(!1)))}_exitAndDetach(){if(this._animationsDisabled||!this.panel){this._detachOverlay();return}this._cleanupDetach?.(),this._cleanupDetach=()=>{t(),clearTimeout(n),this._cleanupDetach=void 0};let e=this.panel.nativeElement,t=this._renderer.listen(e,"animationend",a=>{a.animationName==="_mat-select-exit"&&(this._cleanupDetach?.(),this._detachOverlay())}),n=setTimeout(()=>{this._cleanupDetach?.(),this._detachOverlay()},200);e.classList.add("mat-select-panel-exit")}_detachOverlay(){this._overlayDir.detachOverlay(),this._changeDetectorRef.markForCheck()}writeValue(e){this._assignValue(e)}registerOnChange(e){this._onChange=e}registerOnTouched(e){this._onTouched=e}setDisabledState(e){this.disabled=e,this._changeDetectorRef.markForCheck(),this.stateChanges.next()}get panelOpen(){return this._panelOpen}get selected(){return this.multiple?this._selectionModel?.selected||[]:this._selectionModel?.selected[0]}get triggerValue(){if(this.empty)return"";if(this._multiple){let e=this._selectionModel.selected.map(t=>t.viewValue);return this._isRtl()&&e.reverse(),e.join(", ")}return this._selectionModel.selected[0].viewValue}updateErrorState(){this._errorStateTracker.updateErrorState()}_isRtl(){return this._dir?this._dir.value==="rtl":!1}_handleKeydown(e){this.disabled||(this.panelOpen?this._handleOpenKeydown(e):this._handleClosedKeydown(e))}_handleClosedKeydown(e){let t=e.keyCode,n=t===40||t===38||t===37||t===39,a=t===13||t===32,o=this._keyManager;if(!o.isTyping()&&a&&!le(e)||(this.multiple||e.altKey)&&n)e.preventDefault(),this.open();else if(!this.multiple){let l=this.selected;o.onKeydown(e);let C=this.selected;C&&l!==C&&this._liveAnnouncer.announce(C.viewValue,1e4)}}_handleOpenKeydown(e){let t=this._keyManager,n=e.keyCode,a=n===40||n===38,o=t.isTyping();if(a&&e.altKey)e.preventDefault(),this.close();else if(!o&&(n===13||n===32)&&t.activeItem&&!le(e))e.preventDefault(),t.activeItem._selectViaInteraction();else if(!o&&this._multiple&&n===65&&e.ctrlKey){e.preventDefault();let l=this.options.some(C=>!C.disabled&&!C.selected);this.options.forEach(C=>{C.disabled||(l?C.select():C.deselect())})}else{let l=t.activeItemIndex;t.onKeydown(e),this._multiple&&a&&e.shiftKey&&t.activeItem&&t.activeItemIndex!==l&&t.activeItem._selectViaInteraction()}}_handleOverlayKeydown(e){e.keyCode===27&&!le(e)&&(e.preventDefault(),this.close())}_onFocus(){this.disabled||(this._focused=!0,this.stateChanges.next())}_onBlur(){this._focused=!1,this._keyManager?.cancelTypeahead(),!this.disabled&&!this.panelOpen&&(this._onTouched(),this._changeDetectorRef.markForCheck(),this.stateChanges.next())}get empty(){return!this._selectionModel||this._selectionModel.isEmpty()}_initializeSelection(){Promise.resolve().then(()=>{this.ngControl&&(this._value=this.ngControl.value),this._setSelectionByValue(this._value),this.stateChanges.next()})}_setSelectionByValue(e){if(this.options.forEach(t=>t.setInactiveStyles()),this._selectionModel.clear(),this.multiple&&e)Array.isArray(e),e.forEach(t=>this._selectOptionByValue(t)),this._sortValues();else{let t=this._selectOptionByValue(e);t?this._keyManager.updateActiveItem(t):this.panelOpen||this._keyManager.updateActiveItem(-1)}this._changeDetectorRef.markForCheck()}_selectOptionByValue(e){let t=this.options.find(n=>{if(this._selectionModel.isSelected(n))return!1;try{return(n.value!=null||this.canSelectNullableOptions)&&this._compareWith(n.value,e)}catch{return!1}});return t&&this._selectionModel.select(t),t}_assignValue(e){return e!==this._value||this._multiple&&Array.isArray(e)?(this.options&&this._setSelectionByValue(e),this._value=e,!0):!1}_skipPredicate=e=>this.panelOpen?!1:e.disabled;_getOverlayWidth(e){return this.panelWidth==="auto"?(e instanceof jt?e.elementRef:e||this._elementRef).nativeElement.getBoundingClientRect().width:this.panelWidth===null?"":this.panelWidth}_syncParentProperties(){if(this.options)for(let e of this.options)e._changeDetectorRef.markForCheck()}_initKeyManager(){this._keyManager=new ai(this.options).withTypeAhead(this.typeaheadDebounceInterval).withVerticalOrientation().withHorizontalOrientation(this._isRtl()?"rtl":"ltr").withHomeAndEnd().withPageUpDown().withAllowedModifierKeys(["shiftKey"]).skipPredicate(this._skipPredicate),this._keyManager.tabOut.subscribe(()=>{this.panelOpen&&(!this.multiple&&this._keyManager.activeItem&&this._keyManager.activeItem._selectViaInteraction(),this.focus(),this.close())}),this._keyManager.change.subscribe(()=>{this._panelOpen&&this.panel?this._scrollOptionIntoView(this._keyManager.activeItemIndex||0):!this._panelOpen&&!this.multiple&&this._keyManager.activeItem&&this._keyManager.activeItem._selectViaInteraction()})}_resetOptions(){let e=N(this.options.changes,this._destroy);this.optionSelectionChanges.pipe(y(e)).subscribe(t=>{this._onSelect(t.source,t.isUserInput),t.isUserInput&&!this.multiple&&this._panelOpen&&(this.close(),this.focus())}),N(...this.options.map(t=>t._stateChanges)).pipe(y(e)).subscribe(()=>{this._changeDetectorRef.detectChanges(),this.stateChanges.next()})}_onSelect(e,t){let n=this._selectionModel.isSelected(e);!this.canSelectNullableOptions&&e.value==null&&!this._multiple?(e.deselect(),this._selectionModel.clear(),this.value!=null&&this._propagateChanges(e.value)):(n!==e.selected&&(e.selected?this._selectionModel.select(e):this._selectionModel.deselect(e)),t&&this._keyManager.setActiveItem(e),this.multiple&&(this._sortValues(),t&&this.focus())),n!==this._selectionModel.isSelected(e)&&this._propagateChanges(),this.stateChanges.next()}_sortValues(){if(this.multiple){let e=this.options.toArray();this._selectionModel.sort((t,n)=>this.sortComparator?this.sortComparator(t,n,e):e.indexOf(t)-e.indexOf(n)),this.stateChanges.next()}}_propagateChanges(e){let t;this.multiple?t=this.selected.map(n=>n.value):t=this.selected?this.selected.value:e,this._value=t,this.valueChange.emit(t),this._onChange(t),this.selectionChange.emit(this._getChangeEvent(t)),this._changeDetectorRef.markForCheck()}_highlightCorrectOption(){if(this._keyManager)if(this.empty){let e=-1;for(let t=0;t<this.options.length;t++)if(!this.options.get(t).disabled){e=t;break}this._keyManager.setActiveItem(e)}else this._keyManager.setActiveItem(this._selectionModel.selected[0])}_canOpen(){return!this._panelOpen&&!this.disabled&&this.options?.length>0&&!!this._overlayDir}focus(e){this._elementRef.nativeElement.focus(e)}_getPanelAriaLabelledby(){if(this.ariaLabel)return null;let e=this._parentFormField?.getLabelId()||null,t=e?e+" ":"";return this.ariaLabelledby?t+this.ariaLabelledby:e}_getAriaActiveDescendant(){return this.panelOpen&&this._keyManager&&this._keyManager.activeItem?this._keyManager.activeItem.id:null}_getTriggerAriaLabelledby(){if(this.ariaLabel)return null;let e=this._parentFormField?.getLabelId()||"";return this.ariaLabelledby&&(e+=" "+this.ariaLabelledby),e||(e=this._valueId),e}get describedByIds(){return this._elementRef.nativeElement.getAttribute("aria-describedby")?.split(" ")||[]}setDescribedByIds(e){let t=this._elementRef.nativeElement;e.length?t.setAttribute("aria-describedby",e.join(" ")):t.removeAttribute("aria-describedby")}onContainerClick(e){let t=zn(e);t&&(t.tagName==="MAT-OPTION"||t.classList.contains("cdk-overlay-backdrop")||t.closest(".mat-mdc-select-panel"))||(this.focus(),this.open())}get shouldLabelFloat(){return this.panelOpen||!this.empty||this.focused&&!!this.placeholder}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-select"]],contentQueries:function(t,n,a){if(t&1&&ue(a,Ai,5)(a,wt,5)(a,Ct,5),t&2){let o;d(o=m())&&(n.customTrigger=o.first),d(o=m())&&(n.options=o),d(o=m())&&(n.optionGroups=o)}},viewQuery:function(t,n){if(t&1&&$(bo,5)(_o,5)(Vt,5),t&2){let a;d(a=m())&&(n.trigger=a.first),d(a=m())&&(n.panel=a.first),d(a=m())&&(n._overlayDir=a.first)}},hostAttrs:["role","combobox","aria-haspopup","listbox",1,"mat-mdc-select"],hostVars:21,hostBindings:function(t,n){t&1&&M("keydown",function(o){return n._handleKeydown(o)})("focus",function(){return n._onFocus()})("blur",function(){return n._onBlur()}),t&2&&(T("id",n.id)("tabindex",n.disabled?-1:n.tabIndex)("aria-controls",n.panelOpen?n.id+"-panel":null)("aria-expanded",n.panelOpen)("aria-label",n.ariaLabel||null)("aria-required",n.required.toString())("aria-disabled",n.disabled.toString())("aria-invalid",n.errorState)("aria-activedescendant",n._getAriaActiveDescendant()),g("mat-mdc-select-disabled",n.disabled)("mat-mdc-select-invalid",n.errorState)("mat-mdc-select-required",n.required)("mat-mdc-select-empty",n.empty)("mat-mdc-select-multiple",n.multiple)("mat-select-open",n.panelOpen))},inputs:{userAriaDescribedBy:[0,"aria-describedby","userAriaDescribedBy"],panelClass:"panelClass",disabled:[2,"disabled","disabled",f],disableRipple:[2,"disableRipple","disableRipple",f],tabIndex:[2,"tabIndex","tabIndex",e=>e==null?0:ge(e)],hideSingleSelectionIndicator:[2,"hideSingleSelectionIndicator","hideSingleSelectionIndicator",f],placeholder:"placeholder",required:[2,"required","required",f],multiple:[2,"multiple","multiple",f],disableOptionCentering:[2,"disableOptionCentering","disableOptionCentering",f],compareWith:"compareWith",value:"value",ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"],errorStateMatcher:"errorStateMatcher",typeaheadDebounceInterval:[2,"typeaheadDebounceInterval","typeaheadDebounceInterval",ge],sortComparator:"sortComparator",id:"id",panelWidth:"panelWidth",canSelectNullableOptions:[2,"canSelectNullableOptions","canSelectNullableOptions",f]},outputs:{openedChange:"openedChange",_openedStream:"opened",_closedStream:"closed",selectionChange:"selectionChange",valueChange:"valueChange"},exportAs:["matSelect"],features:[G([{provide:Jt,useExisting:i},{provide:kt,useExisting:i}]),Ye],ngContentSelectors:vo,decls:11,vars:10,consts:[["fallbackOverlayOrigin","cdkOverlayOrigin","trigger",""],["panel",""],["cdk-overlay-origin","",1,"mat-mdc-select-trigger",3,"click"],[1,"mat-mdc-select-value"],[1,"mat-mdc-select-placeholder","mat-mdc-select-min-line"],[1,"mat-mdc-select-value-text"],[1,"mat-mdc-select-arrow-wrapper"],[1,"mat-mdc-select-arrow"],["viewBox","0 0 24 24","width","24px","height","24px","focusable","false","aria-hidden","true"],["d","M7 10l5 5 5-5z"],["cdk-connected-overlay","","cdkConnectedOverlayHasBackdrop","","cdkConnectedOverlayBackdropClass","cdk-overlay-transparent-backdrop",3,"detach","backdropClick","overlayKeydown","cdkConnectedOverlayDisableClose","cdkConnectedOverlayPanelClass","cdkConnectedOverlayScrollStrategy","cdkConnectedOverlayOrigin","cdkConnectedOverlayPositions","cdkConnectedOverlayWidth","cdkConnectedOverlayFlexibleDimensions","cdkConnectedOverlayUsePopover"],[1,"mat-mdc-select-min-line"],["role","listbox","tabindex","-1",1,"mat-mdc-select-panel","mdc-menu-surface","mdc-menu-surface--open",3,"keydown"]],template:function(t,n){if(t&1&&(z(go),h(0,"div",2,0),M("click",function(){return n.open()}),h(3,"div",3),O(4,yo,2,1,"span",4)(5,Co,3,1,"span",5),u(),h(6,"div",6)(7,"div",7),We(),h(8,"svg",8),R(9,"path",9),u()()()(),Ce(10,wo,3,16,"ng-template",10),M("detach",function(){return n.close()})("backdropClick",function(){return n.close()})("overlayKeydown",function(o){return n._handleOverlayKeydown(o)})),t&2){let a=_e(1);c(3),T("id",n._valueId),c(),P(n.empty?4:5),c(6),v("cdkConnectedOverlayDisableClose",!0)("cdkConnectedOverlayPanelClass",n._overlayPanelClass)("cdkConnectedOverlayScrollStrategy",n._scrollStrategy)("cdkConnectedOverlayOrigin",n._preferredOverlayOrigin||a)("cdkConnectedOverlayPositions",n._positions)("cdkConnectedOverlayWidth",n._overlayWidth)("cdkConnectedOverlayFlexibleDimensions",!0)("cdkConnectedOverlayUsePopover",n._popoverLocation)}},dependencies:[jt,Vt],styles:[`@keyframes _mat-select-enter {
  from {
    opacity: 0;
    transform: scaleY(0.8);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@keyframes _mat-select-exit {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}
.mat-mdc-select {
  display: inline-block;
  width: 100%;
  outline: none;
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  color: var(--mat-select-enabled-trigger-text-color, var(--mat-sys-on-surface));
  font-family: var(--mat-select-trigger-text-font, var(--mat-sys-body-large-font));
  line-height: var(--mat-select-trigger-text-line-height, var(--mat-sys-body-large-line-height));
  font-size: var(--mat-select-trigger-text-size, var(--mat-sys-body-large-size));
  font-weight: var(--mat-select-trigger-text-weight, var(--mat-sys-body-large-weight));
  letter-spacing: var(--mat-select-trigger-text-tracking, var(--mat-sys-body-large-tracking));
}

div.mat-mdc-select-panel {
  box-shadow: var(--mat-select-container-elevation-shadow, 0px 3px 1px -2px rgba(0, 0, 0, 0.2), 0px 2px 2px 0px rgba(0, 0, 0, 0.14), 0px 1px 5px 0px rgba(0, 0, 0, 0.12));
}

.mat-mdc-select-disabled {
  color: var(--mat-select-disabled-trigger-text-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mat-mdc-select-disabled .mat-mdc-select-placeholder {
  color: var(--mat-select-disabled-trigger-text-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}

.mat-mdc-select-trigger {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  position: relative;
  box-sizing: border-box;
  width: 100%;
}
.mat-mdc-select-disabled .mat-mdc-select-trigger {
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
}

.mat-mdc-select-value {
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mat-mdc-select-value-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mat-mdc-select-arrow-wrapper {
  height: 24px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
}
.mat-form-field-appearance-fill .mdc-text-field--no-label .mat-mdc-select-arrow-wrapper {
  transform: none;
}

.mat-mdc-form-field .mat-mdc-select.mat-mdc-select-invalid .mat-mdc-select-arrow,
.mat-form-field-invalid:not(.mat-form-field-disabled) .mat-mdc-form-field-infix::after {
  color: var(--mat-select-invalid-arrow-color, var(--mat-sys-error));
}

.mat-mdc-select-arrow {
  width: 10px;
  height: 5px;
  position: relative;
  color: var(--mat-select-enabled-arrow-color, var(--mat-sys-on-surface-variant));
}
.mat-mdc-form-field.mat-focused .mat-mdc-select-arrow {
  color: var(--mat-select-focused-arrow-color, var(--mat-sys-primary));
}
.mat-mdc-form-field .mat-mdc-select.mat-mdc-select-disabled .mat-mdc-select-arrow {
  color: var(--mat-select-disabled-arrow-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
.mat-select-open .mat-mdc-select-arrow {
  transform: rotate(180deg);
}
.mat-form-field-animations-enabled .mat-mdc-select-arrow {
  transition: transform 80ms linear;
}
.mat-mdc-select-arrow svg {
  fill: currentColor;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}
@media (forced-colors: active) {
  .mat-mdc-select-arrow svg {
    fill: CanvasText;
  }
  .mat-mdc-select-disabled .mat-mdc-select-arrow svg {
    fill: GrayText;
  }
}

div.mat-mdc-select-panel {
  width: 100%;
  max-height: 275px;
  outline: 0;
  overflow: auto;
  padding: 8px 0;
  box-sizing: border-box;
  transform-origin: top center;
  border-radius: 0 0 4px 4px;
  position: relative;
  background-color: var(--mat-select-panel-background-color, var(--mat-sys-surface-container));
}
.mat-mdc-select-panel-above div.mat-mdc-select-panel {
  border-radius: 4px 4px 0 0;
  transform-origin: bottom center;
}
@media (forced-colors: active) {
  div.mat-mdc-select-panel {
    outline: solid 1px;
  }
}

.mat-select-panel-animations-enabled {
  animation: _mat-select-enter 120ms cubic-bezier(0, 0, 0.2, 1);
}
.mat-select-panel-animations-enabled.mat-select-panel-exit {
  animation: _mat-select-exit 100ms linear;
}

.mat-mdc-select-placeholder {
  transition: color 400ms 133.3333333333ms cubic-bezier(0.25, 0.8, 0.25, 1);
  color: var(--mat-select-placeholder-text-color, var(--mat-sys-on-surface-variant));
}
.mat-mdc-form-field:not(.mat-form-field-animations-enabled) .mat-mdc-select-placeholder, ._mat-animation-noopable .mat-mdc-select-placeholder {
  transition: none;
}
.mat-form-field-hide-placeholder .mat-mdc-select-placeholder {
  color: transparent;
  -webkit-text-fill-color: transparent;
  transition: none;
  display: block;
}

.mat-mdc-form-field-type-mat-select:not(.mat-form-field-disabled) .mat-mdc-text-field-wrapper {
  cursor: pointer;
}
.mat-mdc-form-field-type-mat-select.mat-form-field-appearance-fill .mat-mdc-floating-label {
  max-width: calc(100% - 18px);
}
.mat-mdc-form-field-type-mat-select.mat-form-field-appearance-fill .mdc-floating-label--float-above {
  max-width: calc(100% / 0.75 - 24px);
}
.mat-mdc-form-field-type-mat-select.mat-form-field-appearance-outline .mdc-notched-outline__notch {
  max-width: calc(100% - 60px);
}
.mat-mdc-form-field-type-mat-select.mat-form-field-appearance-outline .mdc-text-field--label-floating .mdc-notched-outline__notch {
  max-width: calc(100% - 24px);
}

.mat-mdc-select-min-line:empty::before {
  content: " ";
  white-space: pre;
  width: 1px;
  display: inline-block;
  visibility: hidden;
}

.mat-form-field-appearance-fill .mat-mdc-select-arrow-wrapper {
  transform: var(--mat-select-arrow-transform, translateY(-8px));
}
`],encapsulation:2,changeDetection:0})}return i})(),ic=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["mat-select-trigger"]],features:[G([{provide:Ai,useExisting:i}])]})}return i})(),ac=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[qe,Tt,W,Ue,Fi,Tt]})}return i})();var zi=(()=>{class i{httpController;constructor(e){this.httpController=e}getComputes(e){return this.httpController.get(e,"/computes")}getCompute(e,t){return this.httpController.get(e,`/computes/${t}`)}getNetworkInterfaces(e,t){return this.httpController.get(e,`/computes/${t}/network/interfaces`)}createCompute(e,t){return this.httpController.post(e,"/computes",t)}updateCompute(e,t,n){return this.httpController.put(e,`/computes/${t}`,n)}deleteCompute(e,t){return this.httpController.delete(e,`/computes/${t}`)}connectCompute(e,t){return this.httpController.post(e,`/computes/${t}/connect`,null)}disconnectCompute(e,t,n=!1){let a=n?"?force=true":"";return this.httpController.post(e,`/computes/${t}/disconnect${a}`,null)}getStatistics(e){return this.httpController.get(e,"/statistics")}static \u0275fac=function(t){return new(t||i)(X(di))};static \u0275prov=V({token:i,factory:i.\u0275fac})}return i})();var hc=(()=>{class i{computeService;permissionService;WS_LIVENESS_TIMEOUT_MS=15e3;WS_LIVENESS_CHECK_MS=5e3;WS_POLICY_VIOLATION_CLOSE_CODE=1008;NOTIFICATION_STREAM_PRIVILEGE="Notification.Audit";COMPUTE_LIST_PRIVILEGE="Compute.Audit";COMPUTE_POLL_INTERVAL_MS=1e4;ws=null;currentController=null;currentPrivileges=null;intentionalClose=!1;reconnectTimer=null;reconnectAttempt=0;livenessTimer=null;lastWsMessageAt=0;pollTimer=null;computeNotificationEmitter=new p;computeCache=new Map;projectNotificationEmitter=new p;serverSettingsNotificationEmitter=new p;dockerImagePullEmitter=new p;dockerImageDeletedEmitter=new p;wsReconnected=new p;computeCacheUpdated=new p;constructor(e,t){this.computeService=e,this.permissionService=t}notificationsPath(e){let t="ws";return e.protocol==="https:"&&(t="wss"),`${t}://${e.host}:${e.port}/${Ke.current_version}/notifications/ws?token=${e.authToken}`}projectNotificationsPath(e,t){let n="ws";return e.protocol==="https:"&&(n="wss"),`${n}://${e.host}:${e.port}/${Ke.current_version}/projects/${t}/notifications/ws?token=${e.authToken}`}markerNotificationsPath(e,t){let n="ws";return e.protocol==="https:"&&(n="wss"),`${n}://${e.host}:${e.port}/${Ke.current_version}/projects/${t}/notifications/markers/ws?token=${e.authToken}`}connectToComputeNotifications(e){if(this.ws&&this.currentController===e)return;this.disconnect(),this.currentController=e;let t=this.permissionService.cachedPrivileges(e.id);if(t!==null){this.openStreamOrPoll(e,t);return}this.permissionService.ready(e.id).then(n=>this.openStreamOrPoll(e,n)).catch(()=>{this.currentController===e&&this.openComputeNotificationsWs()})}openStreamOrPoll(e,t){this.currentController===e&&(this.currentPrivileges=t,t.has(this.NOTIFICATION_STREAM_PRIVILEGE)?this.openComputeNotificationsWs():this.pollComputesWhenVisible(t))}pollComputesWhenVisible(e){e.has(this.COMPUTE_LIST_PRIVILEGE)&&this.startComputePolling()}handleStreamDenied(){let e=this.currentController;if(!e)return;let t=this.currentPrivileges;if(t!==null){this.pollComputesWhenVisible(t);return}this.permissionService.ready(e.id).then(n=>{this.currentController===e&&(this.currentPrivileges=n,this.pollComputesWhenVisible(n))}).catch(()=>{})}startComputePolling(){this.pollTimer||!this.currentController||(this.pollTimer=setInterval(()=>this.fetchComputesIntoCache(),this.COMPUTE_POLL_INTERVAL_MS),this.fetchComputesIntoCache())}stopComputePolling(){this.pollTimer&&(clearInterval(this.pollTimer),this.pollTimer=null)}fetchComputesIntoCache(){let e=this.currentController;e&&this.computeService.getComputes(e).subscribe({next:t=>this.setInitialComputes(t),error:t=>{if(t?.originalError?.status===403){this.stopComputePolling();return}console.warn("Compute list polling failed",t)}})}openComputeNotificationsWs(){this.currentController&&(this.intentionalClose=!1,this.ws=new WebSocket(this.notificationsPath(this.currentController)),this.ws.onopen=()=>{let e=this.reconnectAttempt>0;this.reconnectAttempt=0,this.startLivenessCheck(),e&&(this.resyncComputesAfterReconnect(),this.wsReconnected.emit())},this.ws.onmessage=e=>{this.lastWsMessageAt=Date.now();let t=JSON.parse(e.data);this.handleMessage(t)},this.ws.onerror=()=>{console.error("Compute notifications WebSocket error")},this.ws.onclose=e=>{if(this.ws=null,this.stopLivenessCheck(),!this.intentionalClose){if(e.code===this.WS_POLICY_VIOLATION_CLOSE_CODE){this.handleStreamDenied();return}this.scheduleReconnect()}})}scheduleReconnect(){if(this.intentionalClose||!this.currentController)return;let e=this.reconnectAttempt++,t=Math.min(3e4,1e3*2**e),n=Math.round(t+Math.random()*.25*t);this.reconnectTimer=setTimeout(()=>this.openComputeNotificationsWs(),n)}resyncComputesAfterReconnect(){this.currentController&&this.computeService.getComputes(this.currentController).subscribe({next:e=>this.setInitialComputes(e),error:e=>console.warn("Compute resync after WS reconnect failed",e)})}startLivenessCheck(){this.stopLivenessCheck(),this.lastWsMessageAt=Date.now(),this.livenessTimer=setInterval(()=>{Date.now()-this.lastWsMessageAt>this.WS_LIVENESS_TIMEOUT_MS&&(console.warn("Compute notifications WS liveness timeout \u2014 no message received, forcing reconnect"),this.stopLivenessCheck(),this.ws?.close())},this.WS_LIVENESS_CHECK_MS)}stopLivenessCheck(){this.livenessTimer&&(clearInterval(this.livenessTimer),this.livenessTimer=null)}disconnect(){this.intentionalClose=!0,this.reconnectTimer&&(clearTimeout(this.reconnectTimer),this.reconnectTimer=null),this.stopLivenessCheck(),this.stopComputePolling(),this.reconnectAttempt=0,this.ws&&(this.ws.close(),this.ws=null),this.currentController=null,this.currentPrivileges=null,this.computeCache.clear()}getCachedComputes(){return Array.from(this.computeCache.values())}hasCachedData(){return this.computeCache.size>0}setInitialComputes(e){this.computeCache.clear(),e.forEach(t=>{this.computeCache.set(t.compute_id,t)}),this.computeCacheUpdated.emit(this.getCachedComputes())}handleMessage(e){switch(e.action){case"compute.created":this.computeCache.set(e.event.compute_id,e.event),this.computeNotificationEmitter.emit(e),this.computeCacheUpdated.emit(this.getCachedComputes());break;case"compute.updated":this.computeCache.set(e.event.compute_id,e.event),this.computeNotificationEmitter.emit(e),this.computeCacheUpdated.emit(this.getCachedComputes());break;case"compute.deleted":this.computeCache.delete(e.event.compute_id),this.computeNotificationEmitter.emit(e),this.computeCacheUpdated.emit(this.getCachedComputes());break;case"project.created":case"project.opened":case"project.closed":case"project.updated":case"project.deleted":this.projectNotificationEmitter.emit(e);break;case"settings.updated":this.serverSettingsNotificationEmitter.emit(e);break;case"docker.image.pull":this.dockerImagePullEmitter.emit(e);break;case"docker.image.deleted":this.dockerImageDeletedEmitter.emit(e);break}}static \u0275fac=function(t){return new(t||i)(X(zi),X(li))};static \u0275prov=V({token:i,factory:i.\u0275fac})}return i})();var Do=["mat-internal-form-field",""],So=["*"],Ni=(()=>{class i{labelPosition="after";static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["div","mat-internal-form-field",""]],hostAttrs:[1,"mdc-form-field","mat-internal-form-field"],hostVars:2,hostBindings:function(t,n){t&2&&g("mdc-form-field--align-end",n.labelPosition==="before")},inputs:{labelPosition:"labelPosition"},attrs:Do,ngContentSelectors:So,decls:1,vars:0,template:function(t,n){t&1&&(z(),k(0))},styles:[`.mat-internal-form-field {
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
}
.mat-internal-form-field > label {
  margin-left: 0;
  margin-right: auto;
  padding-left: 4px;
  padding-right: 0;
  order: 0;
}
[dir=rtl] .mat-internal-form-field > label {
  margin-left: auto;
  margin-right: 0;
  padding-left: 0;
  padding-right: 4px;
}

.mdc-form-field--align-end > label {
  margin-left: auto;
  margin-right: 0;
  padding-left: 0;
  padding-right: 4px;
  order: -1;
}
[dir=rtl] .mdc-form-field--align-end .mdc-form-field--align-end label {
  margin-left: 0;
  margin-right: auto;
  padding-left: 4px;
  padding-right: 0;
}
`],encapsulation:2,changeDetection:0})}return i})();var Eo=["input"],Ro=["label"],Oo=["*"],nn={color:"accent",clickAction:"check-indeterminate",disabledInteractive:!1},Po=new w("mat-checkbox-default-options",{providedIn:"root",factory:()=>nn}),J=(function(i){return i[i.Init=0]="Init",i[i.Checked=1]="Checked",i[i.Unchecked=2]="Unchecked",i[i.Indeterminate=3]="Indeterminate",i})(J||{}),an=class{source;checked},Lo=(()=>{class i{_elementRef=r(I);_changeDetectorRef=r(U);_ngZone=r(B);_animationsDisabled=K();_options=r(Po,{optional:!0});focus(){this._inputElement.nativeElement.focus()}_createChangeEvent(e){let t=new an;return t.source=this,t.checked=e,t}_getAnimationTargetElement(){return this._inputElement?.nativeElement}_animationClasses={uncheckedToChecked:"mdc-checkbox--anim-unchecked-checked",uncheckedToIndeterminate:"mdc-checkbox--anim-unchecked-indeterminate",checkedToUnchecked:"mdc-checkbox--anim-checked-unchecked",checkedToIndeterminate:"mdc-checkbox--anim-checked-indeterminate",indeterminateToChecked:"mdc-checkbox--anim-indeterminate-checked",indeterminateToUnchecked:"mdc-checkbox--anim-indeterminate-unchecked"};ariaLabel="";ariaLabelledby=null;ariaDescribedby;ariaExpanded;ariaControls;ariaOwns;_uniqueId;id;get inputId(){return`${this.id||this._uniqueId}-input`}required=!1;labelPosition="after";name=null;change=new p;indeterminateChange=new p;value;disableRipple=!1;_inputElement;_labelElement;tabIndex;color;disabledInteractive;_onTouched=()=>{};_currentAnimationClass="";_currentCheckState=J.Init;_controlValueAccessorChangeFn=()=>{};_validatorChangeFn=()=>{};constructor(){r(Me).load(Ie);let e=r(new $e("tabindex"),{optional:!0});this._options=this._options||nn,this.color=this._options.color||nn.color,this.tabIndex=e==null?0:parseInt(e)||0,this.id=this._uniqueId=r(q).getId("mat-mdc-checkbox-"),this.disabledInteractive=this._options?.disabledInteractive??!1}ngOnChanges(e){e.required&&this._validatorChangeFn()}ngAfterViewInit(){this._syncIndeterminate(this.indeterminate)}get checked(){return this._checked}set checked(e){e!=this.checked&&(this._checked=e,this._changeDetectorRef.markForCheck())}_checked=!1;get disabled(){return this._disabled}set disabled(e){e!==this.disabled&&(this._disabled=e,this._changeDetectorRef.markForCheck())}_disabled=!1;get indeterminate(){return this._indeterminate()}set indeterminate(e){let t=e!=this._indeterminate();this._indeterminate.set(e),t&&(e?this._transitionCheckState(J.Indeterminate):this._transitionCheckState(this.checked?J.Checked:J.Unchecked),this.indeterminateChange.emit(e)),this._syncIndeterminate(e)}_indeterminate=Z(!1);_isRippleDisabled(){return this.disableRipple||this.disabled}_onLabelTextChange(){this._changeDetectorRef.detectChanges()}writeValue(e){this.checked=!!e}registerOnChange(e){this._controlValueAccessorChangeFn=e}registerOnTouched(e){this._onTouched=e}setDisabledState(e){this.disabled=e}validate(e){return this.required&&e.value!==!0?{required:!0}:null}registerOnValidatorChange(e){this._validatorChangeFn=e}_transitionCheckState(e){let t=this._currentCheckState,n=this._getAnimationTargetElement();if(!(t===e||!n)&&(this._currentAnimationClass&&n.classList.remove(this._currentAnimationClass),this._currentAnimationClass=this._getAnimationClassForCheckStateTransition(t,e),this._currentCheckState=e,this._currentAnimationClass.length>0)){n.classList.add(this._currentAnimationClass);let a=this._currentAnimationClass;this._ngZone.runOutsideAngular(()=>{setTimeout(()=>{n.classList.remove(a)},1e3)})}}_emitChangeEvent(){this._controlValueAccessorChangeFn(this.checked),this.change.emit(this._createChangeEvent(this.checked)),this._inputElement&&(this._inputElement.nativeElement.checked=this.checked)}toggle(){this.checked=!this.checked,this._controlValueAccessorChangeFn(this.checked)}_handleInputClick(){let e=this._options?.clickAction;!this.disabled&&e!=="noop"?(this.indeterminate&&e!=="check"&&Promise.resolve().then(()=>{this._indeterminate.set(!1),this.indeterminateChange.emit(!1)}),this._checked=!this._checked,this._transitionCheckState(this._checked?J.Checked:J.Unchecked),this._emitChangeEvent()):(this.disabled&&this.disabledInteractive||!this.disabled&&e==="noop")&&(this._inputElement.nativeElement.checked=this.checked,this._inputElement.nativeElement.indeterminate=this.indeterminate)}_onInteractionEvent(e){e.stopPropagation()}_onBlur(){Promise.resolve().then(()=>{this._onTouched(),this._changeDetectorRef.markForCheck()})}_getAnimationClassForCheckStateTransition(e,t){if(this._animationsDisabled)return"";switch(e){case J.Init:if(t===J.Checked)return this._animationClasses.uncheckedToChecked;if(t==J.Indeterminate)return this._checked?this._animationClasses.checkedToIndeterminate:this._animationClasses.uncheckedToIndeterminate;break;case J.Unchecked:return t===J.Checked?this._animationClasses.uncheckedToChecked:this._animationClasses.uncheckedToIndeterminate;case J.Checked:return t===J.Unchecked?this._animationClasses.checkedToUnchecked:this._animationClasses.checkedToIndeterminate;case J.Indeterminate:return t===J.Checked?this._animationClasses.indeterminateToChecked:this._animationClasses.indeterminateToUnchecked}return""}_syncIndeterminate(e){let t=this._inputElement;t&&(t.nativeElement.indeterminate=e)}_onInputClick(){this._handleInputClick()}_onTouchTargetClick(){this._handleInputClick(),this.disabled||this._inputElement.nativeElement.focus()}_preventBubblingFromLabel(e){e.target&&this._labelElement.nativeElement.contains(e.target)&&e.stopPropagation()}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-checkbox"]],viewQuery:function(t,n){if(t&1&&$(Eo,5)(Ro,5),t&2){let a;d(a=m())&&(n._inputElement=a.first),d(a=m())&&(n._labelElement=a.first)}},hostAttrs:[1,"mat-mdc-checkbox"],hostVars:16,hostBindings:function(t,n){t&2&&(be("id",n.id),T("tabindex",null)("aria-label",null)("aria-labelledby",null),H(n.color?"mat-"+n.color:"mat-accent"),g("_mat-animation-noopable",n._animationsDisabled)("mdc-checkbox--disabled",n.disabled)("mat-mdc-checkbox-disabled",n.disabled)("mat-mdc-checkbox-checked",n.checked)("mat-mdc-checkbox-disabled-interactive",n.disabledInteractive))},inputs:{ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"],ariaDescribedby:[0,"aria-describedby","ariaDescribedby"],ariaExpanded:[2,"aria-expanded","ariaExpanded",f],ariaControls:[0,"aria-controls","ariaControls"],ariaOwns:[0,"aria-owns","ariaOwns"],id:"id",required:[2,"required","required",f],labelPosition:"labelPosition",name:"name",value:"value",disableRipple:[2,"disableRipple","disableRipple",f],tabIndex:[2,"tabIndex","tabIndex",e=>e==null?void 0:ge(e)],color:"color",disabledInteractive:[2,"disabledInteractive","disabledInteractive",f],checked:[2,"checked","checked",f],disabled:[2,"disabled","disabled",f],indeterminate:[2,"indeterminate","indeterminate",f]},outputs:{change:"change",indeterminateChange:"indeterminateChange"},exportAs:["matCheckbox"],features:[G([{provide:$n,useExisting:yn(()=>i),multi:!0},{provide:Un,useExisting:i,multi:!0}]),Ye],ngContentSelectors:Oo,decls:15,vars:23,consts:[["checkbox",""],["input",""],["label",""],["mat-internal-form-field","",3,"click","labelPosition"],[1,"mdc-checkbox"],["aria-hidden","true",1,"mat-mdc-checkbox-touch-target",3,"click"],["type","checkbox",1,"mdc-checkbox__native-control",3,"blur","click","change","checked","indeterminate","disabled","id","required","tabIndex"],["aria-hidden","true",1,"mdc-checkbox__ripple"],["aria-hidden","true",1,"mdc-checkbox__background"],["focusable","false","viewBox","0 0 24 24",1,"mdc-checkbox__checkmark"],["fill","none","d","M1.73,12.91 8.1,19.28 22.79,4.59",1,"mdc-checkbox__checkmark-path"],[1,"mdc-checkbox__mixedmark"],["mat-ripple","","aria-hidden","true",1,"mat-mdc-checkbox-ripple","mat-focus-indicator",3,"matRippleTrigger","matRippleDisabled","matRippleCentered"],[1,"mdc-label",3,"for"]],template:function(t,n){if(t&1&&(z(),h(0,"div",3),M("click",function(o){return n._preventBubblingFromLabel(o)}),h(1,"div",4,0)(3,"div",5),M("click",function(){return n._onTouchTargetClick()}),u(),h(4,"input",6,1),M("blur",function(){return n._onBlur()})("click",function(){return n._onInputClick()})("change",function(o){return n._onInteractionEvent(o)}),u(),R(6,"div",7),h(7,"div",8),We(),h(8,"svg",9),R(9,"path",10),u(),xn(),R(10,"div",11),u(),R(11,"div",12),u(),h(12,"label",13,2),k(14),u()()),t&2){let a=_e(2);v("labelPosition",n.labelPosition),c(4),g("mdc-checkbox--selected",n.checked),v("checked",n.checked)("indeterminate",n.indeterminate)("disabled",n.disabled&&!n.disabledInteractive)("id",n.inputId)("required",n.required)("tabIndex",n.disabled&&!n.disabledInteractive?-1:n.tabIndex),T("aria-label",n.ariaLabel||null)("aria-labelledby",n.ariaLabelledby)("aria-describedby",n.ariaDescribedby)("aria-checked",n.indeterminate?"mixed":null)("aria-controls",n.ariaControls)("aria-disabled",n.disabled&&n.disabledInteractive?!0:null)("aria-expanded",n.ariaExpanded)("aria-owns",n.ariaOwns)("name",n.name)("value",n.value),c(7),v("matRippleTrigger",a)("matRippleDisabled",n.disableRipple||n.disabled)("matRippleCentered",!0),c(),v("for",n.inputId)}},dependencies:[ce,Ni],styles:[`.mdc-checkbox {
  display: inline-block;
  position: relative;
  flex: 0 0 18px;
  box-sizing: content-box;
  width: 18px;
  height: 18px;
  line-height: 0;
  white-space: nowrap;
  cursor: pointer;
  vertical-align: bottom;
  padding: calc((var(--mat-checkbox-state-layer-size, 40px) - 18px) / 2);
  margin: calc((var(--mat-checkbox-state-layer-size, 40px) - var(--mat-checkbox-state-layer-size, 40px)) / 2);
}
.mdc-checkbox:hover > .mdc-checkbox__ripple {
  opacity: var(--mat-checkbox-unselected-hover-state-layer-opacity, var(--mat-sys-hover-state-layer-opacity));
  background-color: var(--mat-checkbox-unselected-hover-state-layer-color, var(--mat-sys-on-surface));
}
.mdc-checkbox:hover > .mat-mdc-checkbox-ripple > .mat-ripple-element {
  background-color: var(--mat-checkbox-unselected-hover-state-layer-color, var(--mat-sys-on-surface));
}
.mdc-checkbox .mdc-checkbox__native-control:focus + .mdc-checkbox__ripple {
  opacity: var(--mat-checkbox-unselected-focus-state-layer-opacity, var(--mat-sys-focus-state-layer-opacity));
  background-color: var(--mat-checkbox-unselected-focus-state-layer-color, var(--mat-sys-on-surface));
}
.mdc-checkbox .mdc-checkbox__native-control:focus ~ .mat-mdc-checkbox-ripple .mat-ripple-element {
  background-color: var(--mat-checkbox-unselected-focus-state-layer-color, var(--mat-sys-on-surface));
}
.mdc-checkbox:active > .mdc-checkbox__native-control + .mdc-checkbox__ripple {
  opacity: var(--mat-checkbox-unselected-pressed-state-layer-opacity, var(--mat-sys-pressed-state-layer-opacity));
  background-color: var(--mat-checkbox-unselected-pressed-state-layer-color, var(--mat-sys-primary));
}
.mdc-checkbox:active > .mdc-checkbox__native-control ~ .mat-mdc-checkbox-ripple .mat-ripple-element {
  background-color: var(--mat-checkbox-unselected-pressed-state-layer-color, var(--mat-sys-primary));
}
.mdc-checkbox:hover > .mdc-checkbox__native-control:checked + .mdc-checkbox__ripple {
  opacity: var(--mat-checkbox-selected-hover-state-layer-opacity, var(--mat-sys-hover-state-layer-opacity));
  background-color: var(--mat-checkbox-selected-hover-state-layer-color, var(--mat-sys-primary));
}
.mdc-checkbox:hover > .mdc-checkbox__native-control:checked ~ .mat-mdc-checkbox-ripple .mat-ripple-element {
  background-color: var(--mat-checkbox-selected-hover-state-layer-color, var(--mat-sys-primary));
}
.mdc-checkbox .mdc-checkbox__native-control:focus:checked + .mdc-checkbox__ripple {
  opacity: var(--mat-checkbox-selected-focus-state-layer-opacity, var(--mat-sys-focus-state-layer-opacity));
  background-color: var(--mat-checkbox-selected-focus-state-layer-color, var(--mat-sys-primary));
}
.mdc-checkbox .mdc-checkbox__native-control:focus:checked ~ .mat-mdc-checkbox-ripple .mat-ripple-element {
  background-color: var(--mat-checkbox-selected-focus-state-layer-color, var(--mat-sys-primary));
}
.mdc-checkbox:active > .mdc-checkbox__native-control:checked + .mdc-checkbox__ripple {
  opacity: var(--mat-checkbox-selected-pressed-state-layer-opacity, var(--mat-sys-pressed-state-layer-opacity));
  background-color: var(--mat-checkbox-selected-pressed-state-layer-color, var(--mat-sys-on-surface));
}
.mdc-checkbox:active > .mdc-checkbox__native-control:checked ~ .mat-mdc-checkbox-ripple .mat-ripple-element {
  background-color: var(--mat-checkbox-selected-pressed-state-layer-color, var(--mat-sys-on-surface));
}
.mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox .mdc-checkbox__native-control ~ .mat-mdc-checkbox-ripple .mat-ripple-element,
.mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox .mdc-checkbox__native-control + .mdc-checkbox__ripple {
  background-color: var(--mat-checkbox-unselected-hover-state-layer-color, var(--mat-sys-on-surface));
}
.mdc-checkbox .mdc-checkbox__native-control {
  position: absolute;
  margin: 0;
  padding: 0;
  opacity: 0;
  cursor: inherit;
  z-index: 1;
  width: var(--mat-checkbox-state-layer-size, 40px);
  height: var(--mat-checkbox-state-layer-size, 40px);
  top: calc((var(--mat-checkbox-state-layer-size, 40px) - var(--mat-checkbox-state-layer-size, 40px)) / 2);
  right: calc((var(--mat-checkbox-state-layer-size, 40px) - var(--mat-checkbox-state-layer-size, 40px)) / 2);
  left: calc((var(--mat-checkbox-state-layer-size, 40px) - var(--mat-checkbox-state-layer-size, 40px)) / 2);
}

.mdc-checkbox--disabled {
  cursor: default;
  pointer-events: none;
}

.mdc-checkbox__background {
  display: inline-flex;
  position: absolute;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 18px;
  height: 18px;
  border: 2px solid currentColor;
  border-radius: 2px;
  background-color: transparent;
  pointer-events: none;
  will-change: background-color, border-color;
  transition: background-color 90ms cubic-bezier(0.4, 0, 0.6, 1), border-color 90ms cubic-bezier(0.4, 0, 0.6, 1);
  -webkit-print-color-adjust: exact;
  color-adjust: exact;
  border-color: var(--mat-checkbox-unselected-icon-color, var(--mat-sys-on-surface-variant));
  top: calc((var(--mat-checkbox-state-layer-size, 40px) - 18px) / 2);
  left: calc((var(--mat-checkbox-state-layer-size, 40px) - 18px) / 2);
}

.mdc-checkbox__native-control:enabled:checked ~ .mdc-checkbox__background,
.mdc-checkbox__native-control:enabled:indeterminate ~ .mdc-checkbox__background {
  border-color: var(--mat-checkbox-selected-icon-color, var(--mat-sys-primary));
  background-color: var(--mat-checkbox-selected-icon-color, var(--mat-sys-primary));
}

.mdc-checkbox--disabled .mdc-checkbox__background {
  border-color: var(--mat-checkbox-disabled-unselected-icon-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
@media (forced-colors: active) {
  .mdc-checkbox--disabled .mdc-checkbox__background {
    border-color: GrayText;
  }
}

.mdc-checkbox__native-control:disabled:checked ~ .mdc-checkbox__background,
.mdc-checkbox__native-control:disabled:indeterminate ~ .mdc-checkbox__background {
  background-color: var(--mat-checkbox-disabled-selected-icon-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
  border-color: transparent;
}
@media (forced-colors: active) {
  .mdc-checkbox__native-control:disabled:checked ~ .mdc-checkbox__background,
  .mdc-checkbox__native-control:disabled:indeterminate ~ .mdc-checkbox__background {
    border-color: GrayText;
  }
}

.mdc-checkbox:hover > .mdc-checkbox__native-control:not(:checked) ~ .mdc-checkbox__background,
.mdc-checkbox:hover > .mdc-checkbox__native-control:not(:indeterminate) ~ .mdc-checkbox__background {
  border-color: var(--mat-checkbox-unselected-hover-icon-color, var(--mat-sys-on-surface));
  background-color: transparent;
}

.mdc-checkbox:hover > .mdc-checkbox__native-control:checked ~ .mdc-checkbox__background,
.mdc-checkbox:hover > .mdc-checkbox__native-control:indeterminate ~ .mdc-checkbox__background {
  border-color: var(--mat-checkbox-selected-hover-icon-color, var(--mat-sys-primary));
  background-color: var(--mat-checkbox-selected-hover-icon-color, var(--mat-sys-primary));
}

.mdc-checkbox__native-control:focus:focus:not(:checked) ~ .mdc-checkbox__background,
.mdc-checkbox__native-control:focus:focus:not(:indeterminate) ~ .mdc-checkbox__background {
  border-color: var(--mat-checkbox-unselected-focus-icon-color, var(--mat-sys-on-surface));
}

.mdc-checkbox__native-control:focus:focus:checked ~ .mdc-checkbox__background,
.mdc-checkbox__native-control:focus:focus:indeterminate ~ .mdc-checkbox__background {
  border-color: var(--mat-checkbox-selected-focus-icon-color, var(--mat-sys-primary));
  background-color: var(--mat-checkbox-selected-focus-icon-color, var(--mat-sys-primary));
}

.mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox:hover > .mdc-checkbox__native-control ~ .mdc-checkbox__background,
.mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox .mdc-checkbox__native-control:focus ~ .mdc-checkbox__background,
.mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox__background {
  border-color: var(--mat-checkbox-disabled-unselected-icon-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
@media (forced-colors: active) {
  .mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox:hover > .mdc-checkbox__native-control ~ .mdc-checkbox__background,
  .mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox .mdc-checkbox__native-control:focus ~ .mdc-checkbox__background,
  .mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox__background {
    border-color: GrayText;
  }
}
.mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox__native-control:checked ~ .mdc-checkbox__background,
.mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox__native-control:indeterminate ~ .mdc-checkbox__background {
  background-color: var(--mat-checkbox-disabled-selected-icon-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
  border-color: transparent;
}

.mdc-checkbox__checkmark {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  width: 100%;
  opacity: 0;
  transition: opacity 180ms cubic-bezier(0.4, 0, 0.6, 1);
  color: var(--mat-checkbox-selected-checkmark-color, var(--mat-sys-on-primary));
}
@media (forced-colors: active) {
  .mdc-checkbox__checkmark {
    color: CanvasText;
  }
}

.mdc-checkbox--disabled .mdc-checkbox__checkmark, .mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox__checkmark {
  color: var(--mat-checkbox-disabled-selected-checkmark-color, var(--mat-sys-surface));
}
@media (forced-colors: active) {
  .mdc-checkbox--disabled .mdc-checkbox__checkmark, .mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox__checkmark {
    color: GrayText;
  }
}

.mdc-checkbox__checkmark-path {
  transition: stroke-dashoffset 180ms cubic-bezier(0.4, 0, 0.6, 1);
  stroke: currentColor;
  stroke-width: 3.12px;
  stroke-dashoffset: 29.7833385;
  stroke-dasharray: 29.7833385;
}

.mdc-checkbox__mixedmark {
  width: 100%;
  height: 0;
  transform: scaleX(0) rotate(0deg);
  border-width: 1px;
  border-style: solid;
  opacity: 0;
  transition: opacity 90ms cubic-bezier(0.4, 0, 0.6, 1), transform 90ms cubic-bezier(0.4, 0, 0.6, 1);
  border-color: var(--mat-checkbox-selected-checkmark-color, var(--mat-sys-on-primary));
}
@media (forced-colors: active) {
  .mdc-checkbox__mixedmark {
    margin: 0 1px;
  }
}

.mdc-checkbox--disabled .mdc-checkbox__mixedmark, .mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox__mixedmark {
  border-color: var(--mat-checkbox-disabled-selected-checkmark-color, var(--mat-sys-surface));
}
@media (forced-colors: active) {
  .mdc-checkbox--disabled .mdc-checkbox__mixedmark, .mdc-checkbox--disabled.mat-mdc-checkbox-disabled-interactive .mdc-checkbox__mixedmark {
    border-color: GrayText;
  }
}

.mdc-checkbox--anim-unchecked-checked .mdc-checkbox__background,
.mdc-checkbox--anim-unchecked-indeterminate .mdc-checkbox__background,
.mdc-checkbox--anim-checked-unchecked .mdc-checkbox__background,
.mdc-checkbox--anim-indeterminate-unchecked .mdc-checkbox__background {
  animation-duration: 180ms;
  animation-timing-function: linear;
}

.mdc-checkbox--anim-unchecked-checked .mdc-checkbox__checkmark-path {
  animation: mdc-checkbox-unchecked-checked-checkmark-path 180ms linear;
  transition: none;
}

.mdc-checkbox--anim-unchecked-indeterminate .mdc-checkbox__mixedmark {
  animation: mdc-checkbox-unchecked-indeterminate-mixedmark 90ms linear;
  transition: none;
}

.mdc-checkbox--anim-checked-unchecked .mdc-checkbox__checkmark-path {
  animation: mdc-checkbox-checked-unchecked-checkmark-path 90ms linear;
  transition: none;
}

.mdc-checkbox--anim-checked-indeterminate .mdc-checkbox__checkmark {
  animation: mdc-checkbox-checked-indeterminate-checkmark 90ms linear;
  transition: none;
}
.mdc-checkbox--anim-checked-indeterminate .mdc-checkbox__mixedmark {
  animation: mdc-checkbox-checked-indeterminate-mixedmark 90ms linear;
  transition: none;
}

.mdc-checkbox--anim-indeterminate-checked .mdc-checkbox__checkmark {
  animation: mdc-checkbox-indeterminate-checked-checkmark 500ms linear;
  transition: none;
}
.mdc-checkbox--anim-indeterminate-checked .mdc-checkbox__mixedmark {
  animation: mdc-checkbox-indeterminate-checked-mixedmark 500ms linear;
  transition: none;
}

.mdc-checkbox--anim-indeterminate-unchecked .mdc-checkbox__mixedmark {
  animation: mdc-checkbox-indeterminate-unchecked-mixedmark 300ms linear;
  transition: none;
}

.mdc-checkbox__native-control:checked ~ .mdc-checkbox__background,
.mdc-checkbox__native-control:indeterminate ~ .mdc-checkbox__background {
  transition: border-color 90ms cubic-bezier(0, 0, 0.2, 1), background-color 90ms cubic-bezier(0, 0, 0.2, 1);
}
.mdc-checkbox__native-control:checked ~ .mdc-checkbox__background > .mdc-checkbox__checkmark > .mdc-checkbox__checkmark-path,
.mdc-checkbox__native-control:indeterminate ~ .mdc-checkbox__background > .mdc-checkbox__checkmark > .mdc-checkbox__checkmark-path {
  stroke-dashoffset: 0;
}

.mdc-checkbox__native-control:checked ~ .mdc-checkbox__background > .mdc-checkbox__checkmark {
  transition: opacity 180ms cubic-bezier(0, 0, 0.2, 1), transform 180ms cubic-bezier(0, 0, 0.2, 1);
  opacity: 1;
}
.mdc-checkbox__native-control:checked ~ .mdc-checkbox__background > .mdc-checkbox__mixedmark {
  transform: scaleX(1) rotate(-45deg);
}

.mdc-checkbox__native-control:indeterminate ~ .mdc-checkbox__background > .mdc-checkbox__checkmark {
  transform: rotate(45deg);
  opacity: 0;
  transition: opacity 90ms cubic-bezier(0.4, 0, 0.6, 1), transform 90ms cubic-bezier(0.4, 0, 0.6, 1);
}
.mdc-checkbox__native-control:indeterminate ~ .mdc-checkbox__background > .mdc-checkbox__mixedmark {
  transform: scaleX(1) rotate(0deg);
  opacity: 1;
}

@keyframes mdc-checkbox-unchecked-checked-checkmark-path {
  0%, 50% {
    stroke-dashoffset: 29.7833385;
  }
  50% {
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
  }
  100% {
    stroke-dashoffset: 0;
  }
}
@keyframes mdc-checkbox-unchecked-indeterminate-mixedmark {
  0%, 68.2% {
    transform: scaleX(0);
  }
  68.2% {
    animation-timing-function: cubic-bezier(0, 0, 0, 1);
  }
  100% {
    transform: scaleX(1);
  }
}
@keyframes mdc-checkbox-checked-unchecked-checkmark-path {
  from {
    animation-timing-function: cubic-bezier(0.4, 0, 1, 1);
    opacity: 1;
    stroke-dashoffset: 0;
  }
  to {
    opacity: 0;
    stroke-dashoffset: -29.7833385;
  }
}
@keyframes mdc-checkbox-checked-indeterminate-checkmark {
  from {
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    transform: rotate(0deg);
    opacity: 1;
  }
  to {
    transform: rotate(45deg);
    opacity: 0;
  }
}
@keyframes mdc-checkbox-indeterminate-checked-checkmark {
  from {
    animation-timing-function: cubic-bezier(0.14, 0, 0, 1);
    transform: rotate(45deg);
    opacity: 0;
  }
  to {
    transform: rotate(360deg);
    opacity: 1;
  }
}
@keyframes mdc-checkbox-checked-indeterminate-mixedmark {
  from {
    animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    transform: rotate(-45deg);
    opacity: 0;
  }
  to {
    transform: rotate(0deg);
    opacity: 1;
  }
}
@keyframes mdc-checkbox-indeterminate-checked-mixedmark {
  from {
    animation-timing-function: cubic-bezier(0.14, 0, 0, 1);
    transform: rotate(0deg);
    opacity: 1;
  }
  to {
    transform: rotate(315deg);
    opacity: 0;
  }
}
@keyframes mdc-checkbox-indeterminate-unchecked-mixedmark {
  0% {
    animation-timing-function: linear;
    transform: scaleX(1);
    opacity: 1;
  }
  32.8%, 100% {
    transform: scaleX(0);
    opacity: 0;
  }
}
.mat-mdc-checkbox {
  display: inline-block;
  position: relative;
  -webkit-tap-highlight-color: transparent;
}
.mat-mdc-checkbox._mat-animation-noopable > .mat-internal-form-field > .mdc-checkbox > .mat-mdc-checkbox-touch-target,
.mat-mdc-checkbox._mat-animation-noopable > .mat-internal-form-field > .mdc-checkbox > .mdc-checkbox__native-control,
.mat-mdc-checkbox._mat-animation-noopable > .mat-internal-form-field > .mdc-checkbox > .mdc-checkbox__ripple,
.mat-mdc-checkbox._mat-animation-noopable > .mat-internal-form-field > .mdc-checkbox > .mat-mdc-checkbox-ripple::before,
.mat-mdc-checkbox._mat-animation-noopable > .mat-internal-form-field > .mdc-checkbox > .mdc-checkbox__background,
.mat-mdc-checkbox._mat-animation-noopable > .mat-internal-form-field > .mdc-checkbox > .mdc-checkbox__background > .mdc-checkbox__checkmark,
.mat-mdc-checkbox._mat-animation-noopable > .mat-internal-form-field > .mdc-checkbox > .mdc-checkbox__background > .mdc-checkbox__checkmark > .mdc-checkbox__checkmark-path,
.mat-mdc-checkbox._mat-animation-noopable > .mat-internal-form-field > .mdc-checkbox > .mdc-checkbox__background > .mdc-checkbox__mixedmark {
  transition: none !important;
  animation: none !important;
}
.mat-mdc-checkbox label {
  cursor: pointer;
}
.mat-mdc-checkbox .mat-internal-form-field {
  color: var(--mat-checkbox-label-text-color, var(--mat-sys-on-surface));
  font-family: var(--mat-checkbox-label-text-font, var(--mat-sys-body-medium-font));
  line-height: var(--mat-checkbox-label-text-line-height, var(--mat-sys-body-medium-line-height));
  font-size: var(--mat-checkbox-label-text-size, var(--mat-sys-body-medium-size));
  letter-spacing: var(--mat-checkbox-label-text-tracking, var(--mat-sys-body-medium-tracking));
  font-weight: var(--mat-checkbox-label-text-weight, var(--mat-sys-body-medium-weight));
}
.mat-mdc-checkbox.mat-mdc-checkbox-disabled.mat-mdc-checkbox-disabled-interactive {
  pointer-events: auto;
}
.mat-mdc-checkbox.mat-mdc-checkbox-disabled.mat-mdc-checkbox-disabled-interactive input {
  cursor: default;
}
.mat-mdc-checkbox.mat-mdc-checkbox-disabled label {
  cursor: default;
  color: var(--mat-checkbox-disabled-label-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
@media (forced-colors: active) {
  .mat-mdc-checkbox.mat-mdc-checkbox-disabled label {
    color: GrayText;
  }
}
.mat-mdc-checkbox label:empty {
  display: none;
}
.mat-mdc-checkbox .mdc-checkbox__ripple {
  opacity: 0;
}

.mat-mdc-checkbox .mat-mdc-checkbox-ripple,
.mdc-checkbox__ripple {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}
.mat-mdc-checkbox .mat-mdc-checkbox-ripple:not(:empty),
.mdc-checkbox__ripple:not(:empty) {
  transform: translateZ(0);
}

.mat-mdc-checkbox-ripple .mat-ripple-element {
  opacity: 0.1;
}

.mat-mdc-checkbox-touch-target {
  position: absolute;
  top: 50%;
  left: 50%;
  height: var(--mat-checkbox-touch-target-size, 48px);
  width: var(--mat-checkbox-touch-target-size, 48px);
  transform: translate(-50%, -50%);
  display: var(--mat-checkbox-touch-target-display, block);
}

.mat-mdc-checkbox .mat-mdc-checkbox-ripple::before {
  border-radius: 50%;
}

.mdc-checkbox__native-control:focus-visible ~ .mat-focus-indicator::before {
  content: "";
}
`],encapsulation:2,changeDetection:0})}return i})(),Rc=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[Lo,W]})}return i})();var Lc=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[W]})}return i})();var Ze=["*"];function Fo(i,s){i&1&&k(0)}var Vi=["tabListContainer"],Gi=["tabList"],Wi=["tabListInner"],Yi=["nextPaginator"],$i=["previousPaginator"],Ao=["content"];function zo(i,s){}var No=["tabBodyWrapper"],Bo=["tabHeader"];function Ho(i,s){}function jo(i,s){if(i&1&&Ce(0,Ho,0,0,"ng-template",12),i&2){let e=x().$implicit;v("cdkPortalOutlet",e.templateLabel)}}function Vo(i,s){if(i&1&&se(0),i&2){let e=x().$implicit;we(e.textLabel)}}function Go(i,s){if(i&1){let e=Ne();h(0,"div",7,2),M("click",function(){let n=ae(e),a=n.$implicit,o=n.$index,l=x(),C=_e(1);return oe(l._handleClick(a,C,o))})("cdkFocusChange",function(n){let a=ae(e).$index,o=x();return oe(o._tabFocusChanged(n,a))}),R(2,"span",8)(3,"div",9),h(4,"span",10)(5,"span",11),O(6,jo,1,1,null,12)(7,Vo,1,1),u()()()}if(i&2){let e=s.$implicit,t=s.$index,n=_e(1),a=x();H(e.labelClass),g("mdc-tab--active",a.selectedIndex===t),v("id",a._getTabLabelId(e,t))("disabled",e.disabled)("fitInkBarToContent",a.fitInkBarToContent),T("tabIndex",a._getTabIndex(t))("aria-posinset",t+1)("aria-setsize",a._tabs.length)("aria-controls",a._getTabContentId(t))("aria-selected",a.selectedIndex===t)("aria-label",e.ariaLabel||null)("aria-labelledby",!e.ariaLabel&&e.ariaLabelledby?e.ariaLabelledby:null),c(3),v("matRippleTrigger",n)("matRippleDisabled",e.disabled||a.disableRipple),c(3),P(e.templateLabel?6:7)}}function Wo(i,s){i&1&&k(0)}function Yo(i,s){if(i&1){let e=Ne();h(0,"mat-tab-body",13),M("_onCentered",function(){ae(e);let n=x();return oe(n._removeTabBodyWrapperHeight())})("_onCentering",function(n){ae(e);let a=x();return oe(a._setTabBodyWrapperHeight(n))})("_beforeCentering",function(n){ae(e);let a=x();return oe(a._bodyCentered(n))}),u()}if(i&2){let e=s.$implicit,t=s.$index,n=x();H(e.bodyClass),v("id",n._getTabContentId(t))("content",e.content)("position",e.position)("animationDuration",n.animationDuration)("preserveContent",n.preserveContent),T("tabindex",n.contentTabIndex!=null&&n.selectedIndex===t?n.contentTabIndex:null)("aria-labelledby",n._getTabLabelId(e,t))("aria-hidden",n.selectedIndex!==t)}}var $o=["mat-tab-nav-bar",""],Uo=["mat-tab-link",""],Qo=new w("MatTabContent"),qo=(()=>{class i{template=r(Ae);constructor(){}static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["","matTabContent",""]],features:[G([{provide:Qo,useExisting:i}])]})}return i})(),Ko=new w("MatTabLabel"),Ui=new w("MAT_TAB"),Xo=(()=>{class i extends Gn{_closestTab=r(Ui,{optional:!0});static \u0275fac=(()=>{let e;return function(n){return(e||(e=Re(i)))(n||i)}})();static \u0275dir=E({type:i,selectors:[["","mat-tab-label",""],["","matTabLabel",""]],features:[G([{provide:Ko,useExisting:i}]),ke]})}return i})(),Qi=new w("MAT_TAB_GROUP"),Zo=(()=>{class i{_viewContainerRef=r(ze);_closestTabGroup=r(Qi,{optional:!0});disabled=!1;get templateLabel(){return this._templateLabel}set templateLabel(e){this._setTemplateLabelInput(e)}_templateLabel;_explicitContent=void 0;_implicitContent;textLabel="";ariaLabel;ariaLabelledby;labelClass;bodyClass;id=null;_contentPortal=null;get content(){return this._contentPortal}_stateChanges=new _;position=null;origin=null;isActive=!1;constructor(){r(Me).load(Ie)}ngOnChanges(e){(e.hasOwnProperty("textLabel")||e.hasOwnProperty("disabled"))&&this._stateChanges.next()}ngOnDestroy(){this._stateChanges.complete()}ngOnInit(){this._contentPortal=new at(this._explicitContent||this._implicitContent,this._viewContainerRef)}_setTemplateLabelInput(e){e&&e._closestTab===this&&(this._templateLabel=e)}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-tab"]],contentQueries:function(t,n,a){if(t&1&&ue(a,Xo,5)(a,qo,7,Ae),t&2){let o;d(o=m())&&(n.templateLabel=o.first),d(o=m())&&(n._explicitContent=o.first)}},viewQuery:function(t,n){if(t&1&&$(Ae,7),t&2){let a;d(a=m())&&(n._implicitContent=a.first)}},hostAttrs:["hidden",""],hostVars:1,hostBindings:function(t,n){t&2&&T("id",null)},inputs:{disabled:[2,"disabled","disabled",f],textLabel:[0,"label","textLabel"],ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"],labelClass:"labelClass",bodyClass:"bodyClass",id:"id"},exportAs:["matTab"],features:[G([{provide:Ui,useExisting:i}]),Ye],ngContentSelectors:Ze,decls:1,vars:0,template:function(t,n){t&1&&(z(),dt(0,Fo,1,0,"ng-template"))},encapsulation:2})}return i})(),on="mdc-tab-indicator--active",Bi="mdc-tab-indicator--no-transition",St=class{_items;_currentItem;constructor(s){this._items=s}hide(){this._items.forEach(s=>s.deactivateInkBar()),this._currentItem=void 0}alignToElement(s){let e=this._items.find(n=>n.elementRef.nativeElement===s),t=this._currentItem;if(e!==t&&(t?.deactivateInkBar(),e)){let n=t?.elementRef.nativeElement.getBoundingClientRect?.();e.activateInkBar(n),this._currentItem=e}}},qi=(()=>{class i{_elementRef=r(I);_inkBarElement=null;_inkBarContentElement=null;_fitToContent=!1;get fitInkBarToContent(){return this._fitToContent}set fitInkBarToContent(e){this._fitToContent!==e&&(this._fitToContent=e,this._inkBarElement&&this._appendInkBarElement())}activateInkBar(e){let t=this._elementRef.nativeElement;if(!e||!t.getBoundingClientRect||!this._inkBarContentElement){t.classList.add(on);return}let n=t.getBoundingClientRect(),a=e.width/n.width,o=e.left-n.left;t.classList.add(Bi),this._inkBarContentElement.style.setProperty("transform",`translateX(${o}px) scaleX(${a})`),t.getBoundingClientRect(),t.classList.remove(Bi),t.classList.add(on),this._inkBarContentElement.style.setProperty("transform","")}deactivateInkBar(){this._elementRef.nativeElement.classList.remove(on)}ngOnInit(){this._createInkBarElement()}ngOnDestroy(){this._inkBarElement?.remove(),this._inkBarElement=this._inkBarContentElement=null}_createInkBarElement(){let e=this._elementRef.nativeElement.ownerDocument||document,t=this._inkBarElement=e.createElement("span"),n=this._inkBarContentElement=e.createElement("span");t.className="mdc-tab-indicator",n.className="mdc-tab-indicator__content mdc-tab-indicator__content--underline",t.appendChild(this._inkBarContentElement),this._appendInkBarElement()}_appendInkBarElement(){this._inkBarElement;let e=this._fitToContent?this._elementRef.nativeElement.querySelector(".mdc-tab__content"):this._elementRef.nativeElement;e.appendChild(this._inkBarElement)}static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,inputs:{fitInkBarToContent:[2,"fitInkBarToContent","fitInkBarToContent",f]}})}return i})();var Ki=(()=>{class i extends qi{elementRef=r(I);disabled=!1;focus(){this.elementRef.nativeElement.focus()}getOffsetLeft(){return this.elementRef.nativeElement.offsetLeft}getOffsetWidth(){return this.elementRef.nativeElement.offsetWidth}static \u0275fac=(()=>{let e;return function(n){return(e||(e=Re(i)))(n||i)}})();static \u0275dir=E({type:i,selectors:[["","matTabLabelWrapper",""]],hostVars:3,hostBindings:function(t,n){t&2&&(T("aria-disabled",!!n.disabled),g("mat-mdc-tab-disabled",n.disabled))},inputs:{disabled:[2,"disabled","disabled",f]},features:[ke]})}return i})(),Hi={passive:!0},Jo=650,er=100,Xi=(()=>{class i{_elementRef=r(I);_changeDetectorRef=r(U);_viewportRuler=r(it);_dir=r(pe,{optional:!0});_ngZone=r(B);_platform=r(Be);_sharedResizeObserver=r(Mt);_injector=r(re);_renderer=r(te);_animationsDisabled=K();_eventCleanups;_scrollDistance=0;_selectedIndexChanged=!1;_destroyed=new _;_showPaginationControls=!1;_disableScrollAfter=!0;_disableScrollBefore=!0;_tabLabelCount;_scrollDistanceChanged=!1;_keyManager;_currentTextContent;_stopScrolling=new _;disablePagination=!1;get selectedIndex(){return this._selectedIndex}set selectedIndex(e){let t=isNaN(e)?0:e;this._selectedIndex!=t&&(this._selectedIndexChanged=!0,this._selectedIndex=t,this._keyManager&&this._keyManager.updateActiveItem(t))}_selectedIndex=0;selectFocusedIndex=new p;indexFocused=new p;constructor(){this._eventCleanups=this._ngZone.runOutsideAngular(()=>[this._renderer.listen(this._elementRef.nativeElement,"mouseleave",()=>this._stopInterval())])}ngAfterViewInit(){this._eventCleanups.push(this._renderer.listen(this._previousPaginator.nativeElement,"touchstart",()=>this._handlePaginatorPress("before"),Hi),this._renderer.listen(this._nextPaginator.nativeElement,"touchstart",()=>this._handlePaginatorPress("after"),Hi))}ngAfterContentInit(){let e=this._dir?this._dir.change:et("ltr"),t=this._sharedResizeObserver.observe(this._elementRef.nativeElement).pipe(bn(32),y(this._destroyed)),n=this._viewportRuler.change(150).pipe(y(this._destroyed)),a=()=>{this.updatePagination(),this._alignInkBarToSelectedTab()};this._keyManager=new pt(this._items).withHorizontalOrientation(this._getLayoutDirection()).withHomeAndEnd().withWrap().skipPredicate(()=>!1),this._keyManager.updateActiveItem(Math.max(this._selectedIndex,0)),xe(a,{injector:this._injector}),N(e,n,t,this._items.changes,this._itemsResized()).pipe(y(this._destroyed)).subscribe(()=>{this._ngZone.run(()=>{Promise.resolve().then(()=>{this._scrollDistance=Math.max(0,Math.min(this._getMaxScrollDistance(),this._scrollDistance)),a()})}),this._keyManager?.withHorizontalOrientation(this._getLayoutDirection())}),this._keyManager.change.subscribe(o=>{this.indexFocused.emit(o),this._setTabFocus(o)})}_itemsResized(){return typeof ResizeObserver!="function"?mn:this._items.changes.pipe(ee(this._items),Ee(e=>new Se(t=>this._ngZone.runOutsideAngular(()=>{let n=new ResizeObserver(a=>t.next(a));return e.forEach(a=>n.observe(a.elementRef.nativeElement)),()=>{n.disconnect()}}))),gn(1),Q(e=>e.some(t=>t.contentRect.width>0&&t.contentRect.height>0)))}ngAfterContentChecked(){this._tabLabelCount!=this._items.length&&(this.updatePagination(),this._tabLabelCount=this._items.length,this._changeDetectorRef.markForCheck()),this._selectedIndexChanged&&(this._scrollToLabel(this._selectedIndex),this._checkScrollingControls(),this._alignInkBarToSelectedTab(),this._selectedIndexChanged=!1,this._changeDetectorRef.markForCheck()),this._scrollDistanceChanged&&(this._updateTabScrollPosition(),this._scrollDistanceChanged=!1,this._changeDetectorRef.markForCheck())}ngOnDestroy(){this._eventCleanups.forEach(e=>e()),this._keyManager?.destroy(),this._destroyed.next(),this._destroyed.complete(),this._stopScrolling.complete()}_handleKeydown(e){if(!le(e))switch(e.keyCode){case 13:case 32:if(this.focusIndex!==this.selectedIndex){let t=this._items.get(this.focusIndex);t&&!t.disabled&&(this.selectFocusedIndex.emit(this.focusIndex),this._itemSelected(e))}break;default:this._keyManager?.onKeydown(e)}}_onContentChanges(){let e=this._elementRef.nativeElement.textContent;e!==this._currentTextContent&&(this._currentTextContent=e||"",this._ngZone.run(()=>{this.updatePagination(),this._alignInkBarToSelectedTab(),this._changeDetectorRef.markForCheck()}))}updatePagination(){this._checkPaginationEnabled(),this._checkScrollingControls(),this._updateTabScrollPosition()}get focusIndex(){return this._keyManager?this._keyManager.activeItemIndex:0}set focusIndex(e){!this._isValidIndex(e)||this.focusIndex===e||!this._keyManager||this._keyManager.setActiveItem(e)}_isValidIndex(e){return this._items?!!this._items.toArray()[e]:!0}_setTabFocus(e){if(this._showPaginationControls&&this._scrollToLabel(e),this._items&&this._items.length){this._items.toArray()[e].focus();let t=this._tabListContainer.nativeElement;this._getLayoutDirection()=="ltr"?t.scrollLeft=0:t.scrollLeft=t.scrollWidth-t.offsetWidth}}_getLayoutDirection(){return this._dir&&this._dir.value==="rtl"?"rtl":"ltr"}_updateTabScrollPosition(){if(this.disablePagination)return;let e=this.scrollDistance,t=this._getLayoutDirection()==="ltr"?-e:e;this._tabList.nativeElement.style.transform=`translateX(${Math.round(t)}px)`,(this._platform.TRIDENT||this._platform.EDGE)&&(this._tabListContainer.nativeElement.scrollLeft=0)}get scrollDistance(){return this._scrollDistance}set scrollDistance(e){this._scrollTo(e)}_scrollHeader(e){let t=this._tabListContainer.nativeElement.offsetWidth,n=(e=="before"?-1:1)*t/3;return this._scrollTo(this._scrollDistance+n)}_handlePaginatorClick(e){this._stopInterval(),this._scrollHeader(e)}_scrollToLabel(e){if(this.disablePagination)return;let t=this._items?this._items.toArray()[e]:null;if(!t)return;let n=this._tabListContainer.nativeElement.offsetWidth,{offsetLeft:a,offsetWidth:o}=t.elementRef.nativeElement,l,C;this._getLayoutDirection()=="ltr"?(l=a,C=l+o):(C=this._tabListInner.nativeElement.offsetWidth-a,l=C-o);let b=this.scrollDistance,Y=this.scrollDistance+n;l<b?this.scrollDistance-=b-l:C>Y&&(this.scrollDistance+=Math.min(C-Y,l-b))}_checkPaginationEnabled(){if(this.disablePagination)this._showPaginationControls=!1;else{let e=this._tabListInner.nativeElement.scrollWidth,t=this._elementRef.nativeElement.offsetWidth,n=e-t>=5;n||(this.scrollDistance=0),n!==this._showPaginationControls&&(this._showPaginationControls=n,this._changeDetectorRef.markForCheck())}}_checkScrollingControls(){this.disablePagination?this._disableScrollAfter=this._disableScrollBefore=!0:(this._disableScrollBefore=this.scrollDistance==0,this._disableScrollAfter=this.scrollDistance==this._getMaxScrollDistance(),this._changeDetectorRef.markForCheck())}_getMaxScrollDistance(){let e=this._tabListInner.nativeElement.scrollWidth,t=this._tabListContainer.nativeElement.offsetWidth;return e-t||0}_alignInkBarToSelectedTab(){let e=this._items&&this._items.length?this._items.toArray()[this.selectedIndex]:null,t=e?e.elementRef.nativeElement:null;t?this._inkBar.alignToElement(t):this._inkBar.hide()}_stopInterval(){this._stopScrolling.next()}_handlePaginatorPress(e,t){t&&t.button!=null&&t.button!==0||(this._stopInterval(),fn(Jo,er).pipe(y(N(this._stopScrolling,this._destroyed))).subscribe(()=>{let{maxScrollDistance:n,distance:a}=this._scrollHeader(e);(a===0||a>=n)&&this._stopInterval()}))}_scrollTo(e){if(this.disablePagination)return{maxScrollDistance:0,distance:0};let t=this._getMaxScrollDistance();return this._scrollDistance=Math.max(0,Math.min(t,e)),this._scrollDistanceChanged=!0,this._checkScrollingControls(),{maxScrollDistance:t,distance:this._scrollDistance}}static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,inputs:{disablePagination:[2,"disablePagination","disablePagination",f],selectedIndex:[2,"selectedIndex","selectedIndex",ge]},outputs:{selectFocusedIndex:"selectFocusedIndex",indexFocused:"indexFocused"}})}return i})(),tr=(()=>{class i extends Xi{_items;_tabListContainer;_tabList;_tabListInner;_nextPaginator;_previousPaginator;_inkBar;ariaLabel;ariaLabelledby;disableRipple=!1;ngAfterContentInit(){this._inkBar=new St(this._items),super.ngAfterContentInit()}_itemSelected(e){e.preventDefault()}static \u0275fac=(()=>{let e;return function(n){return(e||(e=Re(i)))(n||i)}})();static \u0275cmp=D({type:i,selectors:[["mat-tab-header"]],contentQueries:function(t,n,a){if(t&1&&ue(a,Ki,4),t&2){let o;d(o=m())&&(n._items=o)}},viewQuery:function(t,n){if(t&1&&$(Vi,7)(Gi,7)(Wi,7)(Yi,5)($i,5),t&2){let a;d(a=m())&&(n._tabListContainer=a.first),d(a=m())&&(n._tabList=a.first),d(a=m())&&(n._tabListInner=a.first),d(a=m())&&(n._nextPaginator=a.first),d(a=m())&&(n._previousPaginator=a.first)}},hostAttrs:[1,"mat-mdc-tab-header"],hostVars:4,hostBindings:function(t,n){t&2&&g("mat-mdc-tab-header-pagination-controls-enabled",n._showPaginationControls)("mat-mdc-tab-header-rtl",n._getLayoutDirection()=="rtl")},inputs:{ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"],disableRipple:[2,"disableRipple","disableRipple",f]},features:[ke],ngContentSelectors:Ze,decls:13,vars:10,consts:[["previousPaginator",""],["tabListContainer",""],["tabList",""],["tabListInner",""],["nextPaginator",""],["mat-ripple","",1,"mat-mdc-tab-header-pagination","mat-mdc-tab-header-pagination-before",3,"click","mousedown","touchend","matRippleDisabled"],[1,"mat-mdc-tab-header-pagination-chevron"],[1,"mat-mdc-tab-label-container",3,"keydown"],["role","tablist",1,"mat-mdc-tab-list",3,"cdkObserveContent"],[1,"mat-mdc-tab-labels"],["mat-ripple","",1,"mat-mdc-tab-header-pagination","mat-mdc-tab-header-pagination-after",3,"mousedown","click","touchend","matRippleDisabled"]],template:function(t,n){t&1&&(z(),h(0,"div",5,0),M("click",function(){return n._handlePaginatorClick("before")})("mousedown",function(o){return n._handlePaginatorPress("before",o)})("touchend",function(){return n._stopInterval()}),R(2,"div",6),u(),h(3,"div",7,1),M("keydown",function(o){return n._handleKeydown(o)}),h(5,"div",8,2),M("cdkObserveContent",function(){return n._onContentChanges()}),h(7,"div",9,3),k(9),u()()(),h(10,"div",10,4),M("mousedown",function(o){return n._handlePaginatorPress("after",o)})("click",function(){return n._handlePaginatorClick("after")})("touchend",function(){return n._stopInterval()}),R(12,"div",6),u()),t&2&&(g("mat-mdc-tab-header-pagination-disabled",n._disableScrollBefore),v("matRippleDisabled",n._disableScrollBefore||n.disableRipple),c(3),g("_mat-animation-noopable",n._animationsDisabled),c(2),T("aria-label",n.ariaLabel||null)("aria-labelledby",n.ariaLabelledby||null),c(5),g("mat-mdc-tab-header-pagination-disabled",n._disableScrollAfter),v("matRippleDisabled",n._disableScrollAfter||n.disableRipple))},dependencies:[ce,Gt],styles:[`.mat-mdc-tab-header {
  display: flex;
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
}

.mdc-tab-indicator .mdc-tab-indicator__content {
  transition-duration: var(--mat-tab-animation-duration, 250ms);
}

.mat-mdc-tab-header-pagination {
  -webkit-user-select: none;
  user-select: none;
  position: relative;
  display: none;
  justify-content: center;
  align-items: center;
  min-width: 32px;
  cursor: pointer;
  z-index: 2;
  -webkit-tap-highlight-color: transparent;
  touch-action: none;
  box-sizing: content-box;
  outline: 0;
}
.mat-mdc-tab-header-pagination::-moz-focus-inner {
  border: 0;
}
.mat-mdc-tab-header-pagination .mat-ripple-element {
  opacity: 0.12;
  background-color: var(--mat-tab-inactive-ripple-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-header-pagination-controls-enabled .mat-mdc-tab-header-pagination {
  display: flex;
}

.mat-mdc-tab-header-pagination-before,
.mat-mdc-tab-header-rtl .mat-mdc-tab-header-pagination-after {
  padding-left: 4px;
}
.mat-mdc-tab-header-pagination-before .mat-mdc-tab-header-pagination-chevron,
.mat-mdc-tab-header-rtl .mat-mdc-tab-header-pagination-after .mat-mdc-tab-header-pagination-chevron {
  transform: rotate(-135deg);
}

.mat-mdc-tab-header-rtl .mat-mdc-tab-header-pagination-before,
.mat-mdc-tab-header-pagination-after {
  padding-right: 4px;
}
.mat-mdc-tab-header-rtl .mat-mdc-tab-header-pagination-before .mat-mdc-tab-header-pagination-chevron,
.mat-mdc-tab-header-pagination-after .mat-mdc-tab-header-pagination-chevron {
  transform: rotate(45deg);
}

.mat-mdc-tab-header-pagination-chevron {
  border-style: solid;
  border-width: 2px 2px 0 0;
  height: 8px;
  width: 8px;
  border-color: var(--mat-tab-pagination-icon-color, var(--mat-sys-on-surface));
}

.mat-mdc-tab-header-pagination-disabled {
  box-shadow: none;
  cursor: default;
  pointer-events: none;
}
.mat-mdc-tab-header-pagination-disabled .mat-mdc-tab-header-pagination-chevron {
  opacity: 0.4;
}

.mat-mdc-tab-list {
  flex-grow: 1;
  position: relative;
  transition: transform 500ms cubic-bezier(0.35, 0, 0.25, 1);
}
._mat-animation-noopable .mat-mdc-tab-list {
  transition: none;
}

.mat-mdc-tab-label-container {
  display: flex;
  flex-grow: 1;
  overflow: hidden;
  z-index: 1;
  border-bottom-style: solid;
  border-bottom-width: var(--mat-tab-divider-height, 1px);
  border-bottom-color: var(--mat-tab-divider-color, var(--mat-sys-surface-variant));
}
.mat-mdc-tab-group-inverted-header .mat-mdc-tab-label-container {
  border-bottom: none;
  border-top-style: solid;
  border-top-width: var(--mat-tab-divider-height, 1px);
  border-top-color: var(--mat-tab-divider-color, var(--mat-sys-surface-variant));
}

.mat-mdc-tab-labels {
  display: flex;
  flex: 1 0 auto;
}
[mat-align-tabs=center] > .mat-mdc-tab-header .mat-mdc-tab-labels {
  justify-content: center;
}
[mat-align-tabs=end] > .mat-mdc-tab-header .mat-mdc-tab-labels {
  justify-content: flex-end;
}
.cdk-drop-list .mat-mdc-tab-labels, .mat-mdc-tab-labels.cdk-drop-list {
  min-height: var(--mat-tab-container-height, 48px);
}

.mat-mdc-tab::before {
  margin: 5px;
}
@media (forced-colors: active) {
  .mat-mdc-tab[aria-disabled=true] {
    color: GrayText;
  }
}
`],encapsulation:2})}return i})(),Zi=new w("MAT_TABS_CONFIG"),ji=(()=>{class i extends Ht{_host=r(rn);_ngZone=r(B);_centeringSub=ie.EMPTY;_leavingSub=ie.EMPTY;constructor(){super()}ngOnInit(){super.ngOnInit(),this._centeringSub=this._host._beforeCentering.pipe(ee(this._host._isCenterPosition())).subscribe(e=>{this._host._content&&e&&!this.hasAttached()&&this._ngZone.run(()=>{Promise.resolve().then(),this.attach(this._host._content)})}),this._leavingSub=this._host._afterLeavingCenter.subscribe(()=>{this._host.preserveContent||this._ngZone.run(()=>this.detach())})}ngOnDestroy(){super.ngOnDestroy(),this._centeringSub.unsubscribe(),this._leavingSub.unsubscribe()}static \u0275fac=function(t){return new(t||i)};static \u0275dir=E({type:i,selectors:[["","matTabBodyHost",""]],features:[ke]})}return i})(),rn=(()=>{class i{_elementRef=r(I);_dir=r(pe,{optional:!0});_ngZone=r(B);_injector=r(re);_renderer=r(te);_diAnimationsDisabled=K();_eventCleanups;_initialized=!1;_fallbackTimer;_positionIndex;_dirChangeSubscription=ie.EMPTY;_position;_previousPosition;_onCentering=new p;_beforeCentering=new p;_afterLeavingCenter=new p;_onCentered=new p(!0);_portalHost;_contentElement;_content;animationDuration="500ms";preserveContent=!1;set position(e){this._positionIndex=e,this._computePositionAnimationState()}constructor(){if(this._dir){let e=r(U);this._dirChangeSubscription=this._dir.change.subscribe(t=>{this._computePositionAnimationState(t),e.markForCheck()})}}ngOnInit(){this._bindTransitionEvents(),this._position==="center"&&(this._setActiveClass(!0),xe(()=>this._onCentering.emit(this._elementRef.nativeElement.clientHeight),{injector:this._injector})),this._initialized=!0}ngOnDestroy(){clearTimeout(this._fallbackTimer),this._eventCleanups?.forEach(e=>e()),this._dirChangeSubscription.unsubscribe()}_bindTransitionEvents(){this._ngZone.runOutsideAngular(()=>{let e=this._elementRef.nativeElement,t=n=>{n.target===this._contentElement?.nativeElement&&(this._elementRef.nativeElement.classList.remove("mat-tab-body-animating"),n.type==="transitionend"&&this._transitionDone())};this._eventCleanups=[this._renderer.listen(e,"transitionstart",n=>{n.target===this._contentElement?.nativeElement&&(this._elementRef.nativeElement.classList.add("mat-tab-body-animating"),this._transitionStarted())}),this._renderer.listen(e,"transitionend",t),this._renderer.listen(e,"transitioncancel",t)]})}_transitionStarted(){clearTimeout(this._fallbackTimer);let e=this._position==="center";this._beforeCentering.emit(e),e&&this._onCentering.emit(this._elementRef.nativeElement.clientHeight)}_transitionDone(){this._position==="center"?this._onCentered.emit():this._previousPosition==="center"&&this._afterLeavingCenter.emit()}_setActiveClass(e){this._elementRef.nativeElement.classList.toggle("mat-mdc-tab-body-active",e)}_getLayoutDirection(){return this._dir&&this._dir.value==="rtl"?"rtl":"ltr"}_isCenterPosition(){return this._positionIndex===0}_computePositionAnimationState(e=this._getLayoutDirection()){this._previousPosition=this._position,this._positionIndex<0?this._position=e=="ltr"?"left":"right":this._positionIndex>0?this._position=e=="ltr"?"right":"left":this._position="center",this._animationsDisabled()?this._simulateTransitionEvents():this._initialized&&(this._position==="center"||this._previousPosition==="center")&&(clearTimeout(this._fallbackTimer),this._fallbackTimer=this._ngZone.runOutsideAngular(()=>setTimeout(()=>this._simulateTransitionEvents(),100)))}_simulateTransitionEvents(){this._transitionStarted(),xe(()=>this._transitionDone(),{injector:this._injector})}_animationsDisabled(){return this._diAnimationsDisabled||this.animationDuration==="0ms"||this.animationDuration==="0s"}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-tab-body"]],viewQuery:function(t,n){if(t&1&&$(ji,5)(Ao,5),t&2){let a;d(a=m())&&(n._portalHost=a.first),d(a=m())&&(n._contentElement=a.first)}},hostAttrs:[1,"mat-mdc-tab-body"],hostVars:1,hostBindings:function(t,n){t&2&&T("inert",n._position==="center"?null:"")},inputs:{_content:[0,"content","_content"],animationDuration:"animationDuration",preserveContent:"preserveContent",position:"position"},outputs:{_onCentering:"_onCentering",_beforeCentering:"_beforeCentering",_onCentered:"_onCentered"},decls:3,vars:6,consts:[["content",""],["cdkScrollable","",1,"mat-mdc-tab-body-content"],["matTabBodyHost",""]],template:function(t,n){t&1&&(h(0,"div",1,0),Ce(2,zo,0,0,"ng-template",2),u()),t&2&&g("mat-tab-body-content-left",n._position==="left")("mat-tab-body-content-right",n._position==="right")("mat-tab-body-content-can-animate",n._position==="center"||n._previousPosition==="center")},dependencies:[ji,Hn],styles:[`.mat-mdc-tab-body {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  display: block;
  overflow: hidden;
  outline: 0;
  flex-basis: 100%;
}
.mat-mdc-tab-body.mat-mdc-tab-body-active {
  position: relative;
  overflow-x: hidden;
  overflow-y: auto;
  z-index: 1;
  flex-grow: 1;
}
.mat-mdc-tab-group.mat-mdc-tab-group-dynamic-height .mat-mdc-tab-body.mat-mdc-tab-body-active {
  overflow-y: hidden;
}

.mat-mdc-tab-body-content {
  height: 100%;
  overflow: auto;
  transform: none;
  visibility: hidden;
}
.mat-tab-body-animating > .mat-mdc-tab-body-content, .mat-mdc-tab-body-active > .mat-mdc-tab-body-content {
  visibility: visible;
}
.mat-tab-body-animating > .mat-mdc-tab-body-content {
  min-height: 1px;
}
.mat-mdc-tab-group-dynamic-height .mat-mdc-tab-body-content {
  overflow: hidden;
}

.mat-tab-body-content-can-animate {
  transition: transform var(--mat-tab-animation-duration) 1ms cubic-bezier(0.35, 0, 0.25, 1);
}
.mat-mdc-tab-body-wrapper._mat-animation-noopable .mat-tab-body-content-can-animate {
  transition: none;
}

.mat-tab-body-content-left {
  transform: translate3d(-100%, 0, 0);
}

.mat-tab-body-content-right {
  transform: translate3d(100%, 0, 0);
}
`],encapsulation:2})}return i})(),gd=(()=>{class i{_elementRef=r(I);_changeDetectorRef=r(U);_ngZone=r(B);_tabsSubscription=ie.EMPTY;_tabLabelSubscription=ie.EMPTY;_tabBodySubscription=ie.EMPTY;_diAnimationsDisabled=K();_allTabs;_tabBodies;_tabBodyWrapper;_tabHeader;_tabs=new ct;_indexToSelect=0;_lastFocusedTabIndex=null;_tabBodyWrapperHeight=0;color;get fitInkBarToContent(){return this._fitInkBarToContent}set fitInkBarToContent(e){this._fitInkBarToContent=e,this._changeDetectorRef.markForCheck()}_fitInkBarToContent=!1;stretchTabs=!0;alignTabs=null;dynamicHeight=!1;get selectedIndex(){return this._selectedIndex}set selectedIndex(e){this._indexToSelect=isNaN(e)?null:e}_selectedIndex=null;headerPosition="above";get animationDuration(){return this._animationDuration}set animationDuration(e){let t=e+"";this._animationDuration=/^\d+$/.test(t)?e+"ms":t}_animationDuration;get contentTabIndex(){return this._contentTabIndex}set contentTabIndex(e){this._contentTabIndex=isNaN(e)?null:e}_contentTabIndex=null;disablePagination=!1;disableRipple=!1;preserveContent=!1;get backgroundColor(){return this._backgroundColor}set backgroundColor(e){let t=this._elementRef.nativeElement.classList;t.remove("mat-tabs-with-background",`mat-background-${this.backgroundColor}`),e&&t.add("mat-tabs-with-background",`mat-background-${e}`),this._backgroundColor=e}_backgroundColor;ariaLabel;ariaLabelledby;selectedIndexChange=new p;focusChange=new p;animationDone=new p;selectedTabChange=new p(!0);_groupId;_isServer=!r(Be).isBrowser;constructor(){let e=r(Zi,{optional:!0});this._groupId=r(q).getId("mat-tab-group-"),this.animationDuration=e&&e.animationDuration?e.animationDuration:"500ms",this.disablePagination=e&&e.disablePagination!=null?e.disablePagination:!1,this.dynamicHeight=e&&e.dynamicHeight!=null?e.dynamicHeight:!1,e?.contentTabIndex!=null&&(this.contentTabIndex=e.contentTabIndex),this.preserveContent=!!e?.preserveContent,this.fitInkBarToContent=e&&e.fitInkBarToContent!=null?e.fitInkBarToContent:!1,this.stretchTabs=e&&e.stretchTabs!=null?e.stretchTabs:!0,this.alignTabs=e&&e.alignTabs!=null?e.alignTabs:null}ngAfterContentChecked(){let e=this._indexToSelect=this._clampTabIndex(this._indexToSelect);if(this._selectedIndex!=e){let t=this._selectedIndex==null;if(!t){this.selectedTabChange.emit(this._createChangeEvent(e));let n=this._tabBodyWrapper.nativeElement;n.style.minHeight=n.clientHeight+"px"}Promise.resolve().then(()=>{this._tabs.forEach((n,a)=>n.isActive=a===e),t||(this.selectedIndexChange.emit(e),this._tabBodyWrapper.nativeElement.style.minHeight="")})}this._tabs.forEach((t,n)=>{t.position=n-e,this._selectedIndex!=null&&t.position==0&&!t.origin&&(t.origin=e-this._selectedIndex)}),this._selectedIndex!==e&&(this._selectedIndex=e,this._lastFocusedTabIndex=null,this._changeDetectorRef.markForCheck())}ngAfterContentInit(){this._subscribeToAllTabChanges(),this._subscribeToTabLabels(),this._tabsSubscription=this._tabs.changes.subscribe(()=>{let e=this._clampTabIndex(this._indexToSelect);if(e===this._selectedIndex){let t=this._tabs.toArray(),n;for(let a=0;a<t.length;a++)if(t[a].isActive){this._indexToSelect=this._selectedIndex=a,this._lastFocusedTabIndex=null,n=t[a];break}!n&&t[e]&&Promise.resolve().then(()=>{t[e].isActive=!0,this.selectedTabChange.emit(this._createChangeEvent(e))})}this._changeDetectorRef.markForCheck()})}ngAfterViewInit(){this._tabBodySubscription=this._tabBodies.changes.subscribe(()=>this._bodyCentered(!0))}_subscribeToAllTabChanges(){this._allTabs.changes.pipe(ee(this._allTabs)).subscribe(e=>{this._tabs.reset(e.filter(t=>t._closestTabGroup===this||!t._closestTabGroup)),this._tabs.notifyOnChanges()})}ngOnDestroy(){this._tabs.destroy(),this._tabsSubscription.unsubscribe(),this._tabLabelSubscription.unsubscribe(),this._tabBodySubscription.unsubscribe()}realignInkBar(){this._tabHeader&&this._tabHeader._alignInkBarToSelectedTab()}updatePagination(){this._tabHeader&&this._tabHeader.updatePagination()}focusTab(e){let t=this._tabHeader;t&&(t.focusIndex=e)}_focusChanged(e){this._lastFocusedTabIndex=e,this.focusChange.emit(this._createChangeEvent(e))}_createChangeEvent(e){let t=new sn;return t.index=e,this._tabs&&this._tabs.length&&(t.tab=this._tabs.toArray()[e]),t}_subscribeToTabLabels(){this._tabLabelSubscription&&this._tabLabelSubscription.unsubscribe(),this._tabLabelSubscription=N(...this._tabs.map(e=>e._stateChanges)).subscribe(()=>this._changeDetectorRef.markForCheck())}_clampTabIndex(e){return Math.min(this._tabs.length-1,Math.max(e||0,0))}_getTabLabelId(e,t){return e.id||`${this._groupId}-label-${t}`}_getTabContentId(e){return`${this._groupId}-content-${e}`}_setTabBodyWrapperHeight(e){if(!this.dynamicHeight||!this._tabBodyWrapperHeight){this._tabBodyWrapperHeight=e;return}let t=this._tabBodyWrapper.nativeElement;t.style.height=this._tabBodyWrapperHeight+"px",this._tabBodyWrapper.nativeElement.offsetHeight&&(t.style.height=e+"px")}_removeTabBodyWrapperHeight(){let e=this._tabBodyWrapper.nativeElement;this._tabBodyWrapperHeight=e.clientHeight,e.style.height="",this._ngZone.run(()=>this.animationDone.emit())}_handleClick(e,t,n){t.focusIndex=n,e.disabled||(this.selectedIndex=n)}_getTabIndex(e){let t=this._lastFocusedTabIndex??this.selectedIndex;return e===t?0:-1}_tabFocusChanged(e,t){e&&e!=="mouse"&&e!=="touch"&&(this._tabHeader.focusIndex=t)}_bodyCentered(e){e&&this._tabBodies?.forEach((t,n)=>t._setActiveClass(n===this._selectedIndex))}_animationsDisabled(){return this._diAnimationsDisabled||this.animationDuration==="0"||this.animationDuration==="0ms"}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-tab-group"]],contentQueries:function(t,n,a){if(t&1&&ue(a,Zo,5),t&2){let o;d(o=m())&&(n._allTabs=o)}},viewQuery:function(t,n){if(t&1&&$(No,5)(Bo,5)(rn,5),t&2){let a;d(a=m())&&(n._tabBodyWrapper=a.first),d(a=m())&&(n._tabHeader=a.first),d(a=m())&&(n._tabBodies=a)}},hostAttrs:[1,"mat-mdc-tab-group"],hostVars:11,hostBindings:function(t,n){t&2&&(T("mat-align-tabs",n.alignTabs),H("mat-"+(n.color||"primary")),At("--mat-tab-animation-duration",n.animationDuration),g("mat-mdc-tab-group-dynamic-height",n.dynamicHeight)("mat-mdc-tab-group-inverted-header",n.headerPosition==="below")("mat-mdc-tab-group-stretch-tabs",n.stretchTabs))},inputs:{color:"color",fitInkBarToContent:[2,"fitInkBarToContent","fitInkBarToContent",f],stretchTabs:[2,"mat-stretch-tabs","stretchTabs",f],alignTabs:[0,"mat-align-tabs","alignTabs"],dynamicHeight:[2,"dynamicHeight","dynamicHeight",f],selectedIndex:[2,"selectedIndex","selectedIndex",ge],headerPosition:"headerPosition",animationDuration:"animationDuration",contentTabIndex:[2,"contentTabIndex","contentTabIndex",ge],disablePagination:[2,"disablePagination","disablePagination",f],disableRipple:[2,"disableRipple","disableRipple",f],preserveContent:[2,"preserveContent","preserveContent",f],backgroundColor:"backgroundColor",ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"]},outputs:{selectedIndexChange:"selectedIndexChange",focusChange:"focusChange",animationDone:"animationDone",selectedTabChange:"selectedTabChange"},exportAs:["matTabGroup"],features:[G([{provide:Qi,useExisting:i}])],ngContentSelectors:Ze,decls:9,vars:8,consts:[["tabHeader",""],["tabBodyWrapper",""],["tabNode",""],[3,"indexFocused","selectFocusedIndex","selectedIndex","disableRipple","disablePagination","aria-label","aria-labelledby"],["role","tab","matTabLabelWrapper","","cdkMonitorElementFocus","",1,"mdc-tab","mat-mdc-tab","mat-focus-indicator",3,"id","mdc-tab--active","class","disabled","fitInkBarToContent"],[1,"mat-mdc-tab-body-wrapper"],["role","tabpanel",3,"id","class","content","position","animationDuration","preserveContent"],["role","tab","matTabLabelWrapper","","cdkMonitorElementFocus","",1,"mdc-tab","mat-mdc-tab","mat-focus-indicator",3,"click","cdkFocusChange","id","disabled","fitInkBarToContent"],[1,"mdc-tab__ripple"],["mat-ripple","",1,"mat-mdc-tab-ripple",3,"matRippleTrigger","matRippleDisabled"],[1,"mdc-tab__content"],[1,"mdc-tab__text-label"],[3,"cdkPortalOutlet"],["role","tabpanel",3,"_onCentered","_onCentering","_beforeCentering","id","content","position","animationDuration","preserveContent"]],template:function(t,n){t&1&&(z(),h(0,"mat-tab-header",3,0),M("indexFocused",function(o){return n._focusChanged(o)})("selectFocusedIndex",function(o){return n.selectedIndex=o}),Ot(2,Go,8,17,"div",4,Rt),u(),O(4,Wo,1,0),h(5,"div",5,1),Ot(7,Yo,1,10,"mat-tab-body",6,Rt),u()),t&2&&(v("selectedIndex",n.selectedIndex||0)("disableRipple",n.disableRipple)("disablePagination",n.disablePagination),Dn("aria-label",n.ariaLabel)("aria-labelledby",n.ariaLabelledby),c(2),Pt(n._tabs),c(2),P(n._isServer?4:-1),c(),g("_mat-animation-noopable",n._animationsDisabled()),c(2),Pt(n._tabs))},dependencies:[tr,Ki,Zn,ce,Ht,rn],styles:[`.mdc-tab {
  min-width: 90px;
  padding: 0 24px;
  display: flex;
  flex: 1 0 auto;
  justify-content: center;
  box-sizing: border-box;
  border: none;
  outline: none;
  text-align: center;
  white-space: nowrap;
  cursor: pointer;
  z-index: 1;
  touch-action: manipulation;
}

.mdc-tab__content {
  display: flex;
  align-items: center;
  justify-content: center;
  height: inherit;
  pointer-events: none;
}

.mdc-tab__text-label {
  transition: 150ms color linear;
  display: inline-block;
  line-height: 1;
  z-index: 2;
}

.mdc-tab--active .mdc-tab__text-label {
  transition-delay: 100ms;
}

._mat-animation-noopable .mdc-tab__text-label {
  transition: none;
}

.mdc-tab-indicator {
  display: flex;
  position: absolute;
  top: 0;
  left: 0;
  justify-content: center;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
}

.mdc-tab-indicator__content {
  transition: var(--mat-tab-animation-duration, 250ms) transform cubic-bezier(0.4, 0, 0.2, 1);
  transform-origin: left;
  opacity: 0;
}

.mdc-tab-indicator__content--underline {
  align-self: flex-end;
  box-sizing: border-box;
  width: 100%;
  border-top-style: solid;
}

.mdc-tab-indicator--active .mdc-tab-indicator__content {
  opacity: 1;
}

._mat-animation-noopable .mdc-tab-indicator__content, .mdc-tab-indicator--no-transition .mdc-tab-indicator__content {
  transition: none;
}

.mat-mdc-tab-ripple.mat-mdc-tab-ripple {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  right: 0;
  pointer-events: none;
}

.mat-mdc-tab {
  -webkit-tap-highlight-color: transparent;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-decoration: none;
  background: none;
  height: var(--mat-tab-container-height, 48px);
  font-family: var(--mat-tab-label-text-font, var(--mat-sys-title-small-font));
  font-size: var(--mat-tab-label-text-size, var(--mat-sys-title-small-size));
  letter-spacing: var(--mat-tab-label-text-tracking, var(--mat-sys-title-small-tracking));
  line-height: var(--mat-tab-label-text-line-height, var(--mat-sys-title-small-line-height));
  font-weight: var(--mat-tab-label-text-weight, var(--mat-sys-title-small-weight));
}
.mat-mdc-tab.mdc-tab {
  flex-grow: 0;
}
.mat-mdc-tab .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-active-indicator-color, var(--mat-sys-primary));
  border-top-width: var(--mat-tab-active-indicator-height, 2px);
  border-radius: var(--mat-tab-active-indicator-shape, 0);
}
.mat-mdc-tab:hover .mdc-tab__text-label {
  color: var(--mat-tab-inactive-hover-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab:focus .mdc-tab__text-label {
  color: var(--mat-tab-inactive-focus-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab.mdc-tab--active .mdc-tab__text-label {
  color: var(--mat-tab-active-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab.mdc-tab--active .mdc-tab__ripple::before,
.mat-mdc-tab.mdc-tab--active .mat-ripple-element {
  background-color: var(--mat-tab-active-ripple-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab.mdc-tab--active:hover .mdc-tab__text-label {
  color: var(--mat-tab-active-hover-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab.mdc-tab--active:hover .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-active-hover-indicator-color, var(--mat-sys-primary));
}
.mat-mdc-tab.mdc-tab--active:focus .mdc-tab__text-label {
  color: var(--mat-tab-active-focus-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab.mdc-tab--active:focus .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-active-focus-indicator-color, var(--mat-sys-primary));
}
.mat-mdc-tab.mat-mdc-tab-disabled {
  opacity: 0.4;
  pointer-events: none;
}
.mat-mdc-tab.mat-mdc-tab-disabled .mdc-tab__content {
  pointer-events: none;
}
.mat-mdc-tab.mat-mdc-tab-disabled .mdc-tab__ripple::before,
.mat-mdc-tab.mat-mdc-tab-disabled .mat-ripple-element {
  background-color: var(--mat-tab-disabled-ripple-color, var(--mat-sys-on-surface-variant));
}
.mat-mdc-tab .mdc-tab__ripple::before {
  content: "";
  display: block;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  opacity: 0;
  pointer-events: none;
  background-color: var(--mat-tab-inactive-ripple-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab .mdc-tab__text-label {
  color: var(--mat-tab-inactive-label-text-color, var(--mat-sys-on-surface));
  display: inline-flex;
  align-items: center;
}
.mat-mdc-tab .mdc-tab__content {
  position: relative;
  pointer-events: auto;
}
.mat-mdc-tab:hover .mdc-tab__ripple::before {
  opacity: 0.04;
}
.mat-mdc-tab.cdk-program-focused .mdc-tab__ripple::before, .mat-mdc-tab.cdk-keyboard-focused .mdc-tab__ripple::before {
  opacity: 0.12;
}
.mat-mdc-tab .mat-ripple-element {
  opacity: 0.12;
  background-color: var(--mat-tab-inactive-ripple-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-group.mat-mdc-tab-group-stretch-tabs > .mat-mdc-tab-header .mat-mdc-tab {
  flex-grow: 1;
}

.mat-mdc-tab-group {
  display: flex;
  flex-direction: column;
  max-width: 100%;
}
.mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header, .mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header-pagination {
  background-color: var(--mat-tab-background-color);
}
.mat-mdc-tab-group.mat-tabs-with-background.mat-primary > .mat-mdc-tab-header .mat-mdc-tab .mdc-tab__text-label {
  color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-group.mat-tabs-with-background.mat-primary > .mat-mdc-tab-header .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-group.mat-tabs-with-background:not(.mat-primary) > .mat-mdc-tab-header .mat-mdc-tab:not(.mdc-tab--active) .mdc-tab__text-label {
  color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-group.mat-tabs-with-background:not(.mat-primary) > .mat-mdc-tab-header .mat-mdc-tab:not(.mdc-tab--active) .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header .mat-mdc-tab-header-pagination-chevron,
.mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header .mat-focus-indicator::before, .mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mat-mdc-tab-header-pagination-chevron,
.mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mat-focus-indicator::before {
  border-color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header .mat-ripple-element, .mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header .mdc-tab__ripple::before, .mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mat-ripple-element, .mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mdc-tab__ripple::before {
  background-color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header .mat-mdc-tab-header-pagination-chevron, .mat-mdc-tab-group.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mat-mdc-tab-header-pagination-chevron {
  color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-group.mat-mdc-tab-group-inverted-header {
  flex-direction: column-reverse;
}
.mat-mdc-tab-group.mat-mdc-tab-group-inverted-header .mdc-tab-indicator__content--underline {
  align-self: flex-start;
}

.mat-mdc-tab-body-wrapper {
  position: relative;
  overflow: hidden;
  display: flex;
  transition: height 500ms cubic-bezier(0.35, 0, 0.25, 1);
}
.mat-mdc-tab-body-wrapper._mat-animation-noopable {
  transition: none !important;
  animation: none !important;
}
`],encapsulation:2})}return i})(),sn=class{index;tab},nr=(()=>{class i extends Xi{_focusedItem=Z(null);get fitInkBarToContent(){return this._fitInkBarToContent.value}set fitInkBarToContent(e){this._fitInkBarToContent.next(e),this._changeDetectorRef.markForCheck()}_fitInkBarToContent=new Ve(!1);stretchTabs=!0;get animationDuration(){return this._animationDuration}set animationDuration(e){let t=e+"";this._animationDuration=/^\d+$/.test(t)?e+"ms":t}_animationDuration;_items;get backgroundColor(){return this._backgroundColor}set backgroundColor(e){let t=this._elementRef.nativeElement.classList;t.remove("mat-tabs-with-background",`mat-background-${this.backgroundColor}`),e&&t.add("mat-tabs-with-background",`mat-background-${e}`),this._backgroundColor=e}_backgroundColor;get disableRipple(){return this._disableRipple()}set disableRipple(e){this._disableRipple.set(e)}_disableRipple=Z(!1);color="primary";tabPanel;_tabListContainer;_tabList;_tabListInner;_nextPaginator;_previousPaginator;_inkBar;constructor(){let e=r(Zi,{optional:!0});super(),this.disablePagination=e&&e.disablePagination!=null?e.disablePagination:!1,this.fitInkBarToContent=e&&e.fitInkBarToContent!=null?e.fitInkBarToContent:!1,this.stretchTabs=e&&e.stretchTabs!=null?e.stretchTabs:!0}_itemSelected(){}ngAfterContentInit(){this._inkBar=new St(this._items),this._items.changes.pipe(ee(null),y(this._destroyed)).subscribe(()=>this.updateActiveLink()),super.ngAfterContentInit(),this._keyManager.change.pipe(ee(null),y(this._destroyed)).subscribe(()=>this._focusedItem.set(this._keyManager?.activeItem||null))}ngAfterViewInit(){this.tabPanel,super.ngAfterViewInit()}updateActiveLink(){if(!this._items)return;let e=this._items.toArray();for(let t=0;t<e.length;t++)if(e[t].active){this.selectedIndex=t,this.tabPanel&&(this.tabPanel._activeTabId=e[t].id),this._focusedItem.set(e[t]),this._changeDetectorRef.markForCheck();return}this.selectedIndex=-1}_getRole(){return this.tabPanel?"tablist":this._elementRef.nativeElement.getAttribute("role")}_hasFocus(e){return this._keyManager?.activeItem===e}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["","mat-tab-nav-bar",""]],contentQueries:function(t,n,a){if(t&1&&ue(a,ir,5),t&2){let o;d(o=m())&&(n._items=o)}},viewQuery:function(t,n){if(t&1&&$(Vi,7)(Gi,7)(Wi,7)(Yi,5)($i,5),t&2){let a;d(a=m())&&(n._tabListContainer=a.first),d(a=m())&&(n._tabList=a.first),d(a=m())&&(n._tabListInner=a.first),d(a=m())&&(n._nextPaginator=a.first),d(a=m())&&(n._previousPaginator=a.first)}},hostAttrs:[1,"mat-mdc-tab-nav-bar","mat-mdc-tab-header"],hostVars:17,hostBindings:function(t,n){t&2&&(T("role",n._getRole()),At("--mat-tab-animation-duration",n.animationDuration),g("mat-mdc-tab-header-pagination-controls-enabled",n._showPaginationControls)("mat-mdc-tab-header-rtl",n._getLayoutDirection()=="rtl")("mat-mdc-tab-nav-bar-stretch-tabs",n.stretchTabs)("mat-primary",n.color!=="warn"&&n.color!=="accent")("mat-accent",n.color==="accent")("mat-warn",n.color==="warn")("_mat-animation-noopable",n._animationsDisabled))},inputs:{fitInkBarToContent:[2,"fitInkBarToContent","fitInkBarToContent",f],stretchTabs:[2,"mat-stretch-tabs","stretchTabs",f],animationDuration:"animationDuration",backgroundColor:"backgroundColor",disableRipple:[2,"disableRipple","disableRipple",f],color:"color",tabPanel:"tabPanel"},exportAs:["matTabNavBar","matTabNav"],features:[ke],attrs:$o,ngContentSelectors:Ze,decls:13,vars:6,consts:[["previousPaginator",""],["tabListContainer",""],["tabList",""],["tabListInner",""],["nextPaginator",""],["mat-ripple","",1,"mat-mdc-tab-header-pagination","mat-mdc-tab-header-pagination-before",3,"click","mousedown","touchend","matRippleDisabled"],[1,"mat-mdc-tab-header-pagination-chevron"],[1,"mat-mdc-tab-link-container",3,"keydown"],[1,"mat-mdc-tab-list",3,"cdkObserveContent"],[1,"mat-mdc-tab-links"],["mat-ripple","",1,"mat-mdc-tab-header-pagination","mat-mdc-tab-header-pagination-after",3,"mousedown","click","touchend","matRippleDisabled"]],template:function(t,n){t&1&&(z(),h(0,"div",5,0),M("click",function(){return n._handlePaginatorClick("before")})("mousedown",function(o){return n._handlePaginatorPress("before",o)})("touchend",function(){return n._stopInterval()}),R(2,"div",6),u(),h(3,"div",7,1),M("keydown",function(o){return n._handleKeydown(o)}),h(5,"div",8,2),M("cdkObserveContent",function(){return n._onContentChanges()}),h(7,"div",9,3),k(9),u()()(),h(10,"div",10,4),M("mousedown",function(o){return n._handlePaginatorPress("after",o)})("click",function(){return n._handlePaginatorClick("after")})("touchend",function(){return n._stopInterval()}),R(12,"div",6),u()),t&2&&(g("mat-mdc-tab-header-pagination-disabled",n._disableScrollBefore),v("matRippleDisabled",n._disableScrollBefore||n.disableRipple),c(10),g("mat-mdc-tab-header-pagination-disabled",n._disableScrollAfter),v("matRippleDisabled",n._disableScrollAfter||n.disableRipple))},dependencies:[ce,Gt],styles:[`.mdc-tab {
  min-width: 90px;
  padding: 0 24px;
  display: flex;
  flex: 1 0 auto;
  justify-content: center;
  box-sizing: border-box;
  border: none;
  outline: none;
  text-align: center;
  white-space: nowrap;
  cursor: pointer;
  z-index: 1;
  touch-action: manipulation;
}

.mdc-tab__content {
  display: flex;
  align-items: center;
  justify-content: center;
  height: inherit;
  pointer-events: none;
}

.mdc-tab__text-label {
  transition: 150ms color linear;
  display: inline-block;
  line-height: 1;
  z-index: 2;
}

.mdc-tab--active .mdc-tab__text-label {
  transition-delay: 100ms;
}

._mat-animation-noopable .mdc-tab__text-label {
  transition: none;
}

.mdc-tab-indicator {
  display: flex;
  position: absolute;
  top: 0;
  left: 0;
  justify-content: center;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
}

.mdc-tab-indicator__content {
  transition: var(--mat-tab-animation-duration, 250ms) transform cubic-bezier(0.4, 0, 0.2, 1);
  transform-origin: left;
  opacity: 0;
}

.mdc-tab-indicator__content--underline {
  align-self: flex-end;
  box-sizing: border-box;
  width: 100%;
  border-top-style: solid;
}

.mdc-tab-indicator--active .mdc-tab-indicator__content {
  opacity: 1;
}

._mat-animation-noopable .mdc-tab-indicator__content, .mdc-tab-indicator--no-transition .mdc-tab-indicator__content {
  transition: none;
}

.mat-mdc-tab-ripple.mat-mdc-tab-ripple {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  right: 0;
  pointer-events: none;
}

.mat-mdc-tab-header {
  display: flex;
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
}

.mdc-tab-indicator .mdc-tab-indicator__content {
  transition-duration: var(--mat-tab-animation-duration, 250ms);
}

.mat-mdc-tab-header-pagination {
  -webkit-user-select: none;
  user-select: none;
  position: relative;
  display: none;
  justify-content: center;
  align-items: center;
  min-width: 32px;
  cursor: pointer;
  z-index: 2;
  -webkit-tap-highlight-color: transparent;
  touch-action: none;
  box-sizing: content-box;
  outline: 0;
}
.mat-mdc-tab-header-pagination::-moz-focus-inner {
  border: 0;
}
.mat-mdc-tab-header-pagination .mat-ripple-element {
  opacity: 0.12;
  background-color: var(--mat-tab-inactive-ripple-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-header-pagination-controls-enabled .mat-mdc-tab-header-pagination {
  display: flex;
}

.mat-mdc-tab-header-pagination-before,
.mat-mdc-tab-header-rtl .mat-mdc-tab-header-pagination-after {
  padding-left: 4px;
}
.mat-mdc-tab-header-pagination-before .mat-mdc-tab-header-pagination-chevron,
.mat-mdc-tab-header-rtl .mat-mdc-tab-header-pagination-after .mat-mdc-tab-header-pagination-chevron {
  transform: rotate(-135deg);
}

.mat-mdc-tab-header-rtl .mat-mdc-tab-header-pagination-before,
.mat-mdc-tab-header-pagination-after {
  padding-right: 4px;
}
.mat-mdc-tab-header-rtl .mat-mdc-tab-header-pagination-before .mat-mdc-tab-header-pagination-chevron,
.mat-mdc-tab-header-pagination-after .mat-mdc-tab-header-pagination-chevron {
  transform: rotate(45deg);
}

.mat-mdc-tab-header-pagination-chevron {
  border-style: solid;
  border-width: 2px 2px 0 0;
  height: 8px;
  width: 8px;
  border-color: var(--mat-tab-pagination-icon-color, var(--mat-sys-on-surface));
}

.mat-mdc-tab-header-pagination-disabled {
  box-shadow: none;
  cursor: default;
  pointer-events: none;
}
.mat-mdc-tab-header-pagination-disabled .mat-mdc-tab-header-pagination-chevron {
  opacity: 0.4;
}

.mat-mdc-tab-list {
  flex-grow: 1;
  position: relative;
  transition: transform 500ms cubic-bezier(0.35, 0, 0.25, 1);
}
._mat-animation-noopable .mat-mdc-tab-list {
  transition: none;
}

.mat-mdc-tab-links {
  display: flex;
  flex: 1 0 auto;
}
[mat-align-tabs=center] > .mat-mdc-tab-link-container .mat-mdc-tab-links {
  justify-content: center;
}
[mat-align-tabs=end] > .mat-mdc-tab-link-container .mat-mdc-tab-links {
  justify-content: flex-end;
}
.cdk-drop-list .mat-mdc-tab-links, .mat-mdc-tab-links.cdk-drop-list {
  min-height: var(--mat-tab-container-height, 48px);
}

.mat-mdc-tab-link-container {
  display: flex;
  flex-grow: 1;
  overflow: hidden;
  z-index: 1;
  border-bottom-style: solid;
  border-bottom-width: var(--mat-tab-divider-height, 1px);
  border-bottom-color: var(--mat-tab-divider-color, var(--mat-sys-surface-variant));
}

.mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-link-container, .mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-header-pagination {
  background-color: var(--mat-tab-background-color);
}
.mat-mdc-tab-nav-bar.mat-tabs-with-background.mat-primary > .mat-mdc-tab-link-container .mat-mdc-tab-link .mdc-tab__text-label {
  color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-nav-bar.mat-tabs-with-background.mat-primary > .mat-mdc-tab-link-container .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-nav-bar.mat-tabs-with-background:not(.mat-primary) > .mat-mdc-tab-link-container .mat-mdc-tab-link:not(.mdc-tab--active) .mdc-tab__text-label {
  color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-nav-bar.mat-tabs-with-background:not(.mat-primary) > .mat-mdc-tab-link-container .mat-mdc-tab-link:not(.mdc-tab--active) .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-link-container .mat-mdc-tab-header-pagination-chevron,
.mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-link-container .mat-focus-indicator::before, .mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mat-mdc-tab-header-pagination-chevron,
.mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mat-focus-indicator::before {
  border-color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-link-container .mat-ripple-element, .mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-link-container .mdc-tab__ripple::before, .mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mat-ripple-element, .mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mdc-tab__ripple::before {
  background-color: var(--mat-tab-foreground-color);
}
.mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-link-container .mat-mdc-tab-header-pagination-chevron, .mat-mdc-tab-nav-bar.mat-tabs-with-background > .mat-mdc-tab-header-pagination .mat-mdc-tab-header-pagination-chevron {
  color: var(--mat-tab-foreground-color);
}
`],encapsulation:2})}return i})(),ir=(()=>{class i extends qi{_tabNavBar=r(nr);elementRef=r(I);_focusMonitor=r(He);_destroyed=new _;_isActive=!1;_tabIndex=Pe(()=>this._tabNavBar._focusedItem()===this?this.tabIndex:-1);get active(){return this._isActive}set active(e){e!==this._isActive&&(this._isActive=e,this._tabNavBar.updateActiveLink())}disabled=!1;get disableRipple(){return this._disableRipple()}set disableRipple(e){this._disableRipple.set(e)}_disableRipple=Z(!1);tabIndex=0;rippleConfig;get rippleDisabled(){return this.disabled||this.disableRipple||this._tabNavBar.disableRipple||!!this.rippleConfig.disabled}id=r(q).getId("mat-tab-link-");constructor(){super(),r(Me).load(Ie);let e=r(Yt,{optional:!0}),t=r(new $e("tabindex"),{optional:!0});this.rippleConfig=e||{},this.tabIndex=t==null?0:parseInt(t)||0,K()&&(this.rippleConfig.animation={enterDuration:0,exitDuration:0}),this._tabNavBar._fitInkBarToContent.pipe(y(this._destroyed)).subscribe(n=>{this.fitInkBarToContent=n})}focus(){this.elementRef.nativeElement.focus()}ngAfterViewInit(){this._focusMonitor.monitor(this.elementRef)}ngOnDestroy(){this._destroyed.next(),this._destroyed.complete(),super.ngOnDestroy(),this._focusMonitor.stopMonitoring(this.elementRef)}_handleFocus(){this._tabNavBar.focusIndex=this._tabNavBar._items.toArray().indexOf(this)}_handleKeydown(e){(e.keyCode===32||e.keyCode===13)&&(this.disabled?e.preventDefault():this._tabNavBar.tabPanel&&(e.keyCode===32&&e.preventDefault(),this.elementRef.nativeElement.click()))}_getAriaControls(){return this._tabNavBar.tabPanel?this._tabNavBar.tabPanel?.id:this.elementRef.nativeElement.getAttribute("aria-controls")}_getAriaSelected(){return this._tabNavBar.tabPanel?this.active?"true":"false":this.elementRef.nativeElement.getAttribute("aria-selected")}_getAriaCurrent(){return this.active&&!this._tabNavBar.tabPanel?"page":null}_getRole(){return this._tabNavBar.tabPanel?"tab":this.elementRef.nativeElement.getAttribute("role")}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["","mat-tab-link",""],["","matTabLink",""]],hostAttrs:[1,"mdc-tab","mat-mdc-tab-link","mat-focus-indicator"],hostVars:11,hostBindings:function(t,n){t&1&&M("focus",function(){return n._handleFocus()})("keydown",function(o){return n._handleKeydown(o)}),t&2&&(T("aria-controls",n._getAriaControls())("aria-current",n._getAriaCurrent())("aria-disabled",n.disabled)("aria-selected",n._getAriaSelected())("id",n.id)("tabIndex",n._tabIndex())("role",n._getRole()),g("mat-mdc-tab-disabled",n.disabled)("mdc-tab--active",n.active))},inputs:{active:[2,"active","active",f],disabled:[2,"disabled","disabled",f],disableRipple:[2,"disableRipple","disableRipple",f],tabIndex:[2,"tabIndex","tabIndex",e=>e==null?0:ge(e)],id:"id"},exportAs:["matTabLink"],features:[ke],attrs:Uo,ngContentSelectors:Ze,decls:5,vars:2,consts:[[1,"mdc-tab__ripple"],["mat-ripple","",1,"mat-mdc-tab-ripple",3,"matRippleTrigger","matRippleDisabled"],[1,"mdc-tab__content"],[1,"mdc-tab__text-label"]],template:function(t,n){t&1&&(z(),R(0,"span",0)(1,"div",1),h(2,"span",2)(3,"span",3),k(4),u()()),t&2&&(c(),v("matRippleTrigger",n.elementRef.nativeElement)("matRippleDisabled",n.rippleDisabled))},dependencies:[ce],styles:[`.mat-mdc-tab-link {
  -webkit-tap-highlight-color: transparent;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-decoration: none;
  background: none;
  height: var(--mat-tab-container-height, 48px);
  font-family: var(--mat-tab-label-text-font, var(--mat-sys-title-small-font));
  font-size: var(--mat-tab-label-text-size, var(--mat-sys-title-small-size));
  letter-spacing: var(--mat-tab-label-text-tracking, var(--mat-sys-title-small-tracking));
  line-height: var(--mat-tab-label-text-line-height, var(--mat-sys-title-small-line-height));
  font-weight: var(--mat-tab-label-text-weight, var(--mat-sys-title-small-weight));
}
.mat-mdc-tab-link.mdc-tab {
  flex-grow: 0;
}
.mat-mdc-tab-link .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-active-indicator-color, var(--mat-sys-primary));
  border-top-width: var(--mat-tab-active-indicator-height, 2px);
  border-radius: var(--mat-tab-active-indicator-shape, 0);
}
.mat-mdc-tab-link:hover .mdc-tab__text-label {
  color: var(--mat-tab-inactive-hover-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-link:focus .mdc-tab__text-label {
  color: var(--mat-tab-inactive-focus-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-link.mdc-tab--active .mdc-tab__text-label {
  color: var(--mat-tab-active-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-link.mdc-tab--active .mdc-tab__ripple::before,
.mat-mdc-tab-link.mdc-tab--active .mat-ripple-element {
  background-color: var(--mat-tab-active-ripple-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-link.mdc-tab--active:hover .mdc-tab__text-label {
  color: var(--mat-tab-active-hover-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-link.mdc-tab--active:hover .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-active-hover-indicator-color, var(--mat-sys-primary));
}
.mat-mdc-tab-link.mdc-tab--active:focus .mdc-tab__text-label {
  color: var(--mat-tab-active-focus-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-link.mdc-tab--active:focus .mdc-tab-indicator__content--underline {
  border-color: var(--mat-tab-active-focus-indicator-color, var(--mat-sys-primary));
}
.mat-mdc-tab-link.mat-mdc-tab-disabled {
  opacity: 0.4;
  pointer-events: none;
}
.mat-mdc-tab-link.mat-mdc-tab-disabled .mdc-tab__content {
  pointer-events: none;
}
.mat-mdc-tab-link.mat-mdc-tab-disabled .mdc-tab__ripple::before,
.mat-mdc-tab-link.mat-mdc-tab-disabled .mat-ripple-element {
  background-color: var(--mat-tab-disabled-ripple-color, var(--mat-sys-on-surface-variant));
}
.mat-mdc-tab-link .mdc-tab__ripple::before {
  content: "";
  display: block;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  opacity: 0;
  pointer-events: none;
  background-color: var(--mat-tab-inactive-ripple-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-link .mdc-tab__text-label {
  color: var(--mat-tab-inactive-label-text-color, var(--mat-sys-on-surface));
  display: inline-flex;
  align-items: center;
}
.mat-mdc-tab-link .mdc-tab__content {
  position: relative;
  pointer-events: auto;
}
.mat-mdc-tab-link:hover .mdc-tab__ripple::before {
  opacity: 0.04;
}
.mat-mdc-tab-link.cdk-program-focused .mdc-tab__ripple::before, .mat-mdc-tab-link.cdk-keyboard-focused .mdc-tab__ripple::before {
  opacity: 0.12;
}
.mat-mdc-tab-link .mat-ripple-element {
  opacity: 0.12;
  background-color: var(--mat-tab-inactive-ripple-color, var(--mat-sys-on-surface));
}
.mat-mdc-tab-header.mat-mdc-tab-nav-bar-stretch-tabs .mat-mdc-tab-link {
  flex-grow: 1;
}
.mat-mdc-tab-link::before {
  margin: 5px;
}

@media (max-width: 599px) {
  .mat-mdc-tab-link {
    min-width: 72px;
  }
}
`],encapsulation:2,changeDetection:0})}return i})(),vd=(()=>{class i{id=r(q).getId("mat-tab-nav-panel-");_activeTabId;static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-tab-nav-panel"]],hostAttrs:["role","tabpanel",1,"mat-mdc-tab-nav-panel"],hostVars:2,hostBindings:function(t,n){t&2&&T("aria-labelledby",n._activeTabId)("id",n.id)},inputs:{id:"id"},exportAs:["matTabNavPanel"],ngContentSelectors:Ze,decls:1,vars:0,template:function(t,n){t&1&&(z(),k(0))},encapsulation:2,changeDetection:0})}return i})(),yd=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[W]})}return i})();var Je=class{data=[];keyIndex=new Map;dataChange=new Ve([]);itemUpdated=new _;getItems(){return this.data}add(s){if(this.findIndex(s)>=0){this.update(s);return}this.data=[...this.data,s],this.keyIndex.set(this.getItemKey(s),this.data.length-1),this.dataChange.next(this.data)}set(s){let e=[];for(let t of s||[]){let n=this.getItemKey(t),a=this.keyIndex.get(n);e.push(a!==void 0?Object.assign(this.data[a],t):t)}this.data=e,this.reindex(),this.dataChange.next(this.data)}get(s){let e=this.keyIndex.get(s);if(e!==void 0)return this.data[e]}update(s){let e=this.findIndex(s);if(e>=0){let t=Object.assign(this.data[e],s);this.data=[...this.data],this.data[e]=t,this.dataChange.next(this.data),this.itemUpdated.next(t)}}remove(s){let e=this.findIndex(s);e>=0&&(this.data=this.data.filter((t,n)=>n!==e),this.reindex(),this.dataChange.next(this.data))}applyBatch(s,e){if(s.length>0){let t=this.data.length;this.data=[...this.data,...s];for(let n=0;n<s.length;n++)this.keyIndex.set(this.getItemKey(s[n]),t+n)}if(e.length>0){let t=new Set(e.map(n=>this.getItemKey(n)));this.data=this.data.filter(n=>!t.has(this.getItemKey(n))),this.reindex()}else s.length===0&&(this.data=[...this.data]);this.dataChange.next(this.data)}get changes(){return this.dataChange}get itemChanged(){return this.itemUpdated}clear(){this.data=[],this.keyIndex.clear(),this.dataChange.next(this.data)}reindex(){this.keyIndex.clear();for(let s=0;s<this.data.length;s++)this.keyIndex.set(this.getItemKey(this.data[s]),s)}findIndex(s){let e=this.keyIndex.get(this.getItemKey(s));return e===void 0?-1:e}};var Td=(()=>{class i extends Je{getItemKey(e){return e.link_id}static \u0275fac=(()=>{let e;return function(n){return(e||(e=Re(i)))(n||i)}})();static \u0275prov=V({token:i,factory:i.\u0275fac})}return i})();var or=new w("DEFAULT_THEME_TOKEN",{providedIn:"root",factory:()=>"indigo-pink"}),Ji=(()=>{class i{document;userPreferences;_darkMode$=new Ve(!1);darkMode$=this._darkMode$.asObservable();themeChanged=new p;mapThemeChanged=new p;currentTheme="indigo-pink";currentMapTheme="auto";savedTheme="indigo-pink";savedMapTheme="auto";availableThemes=[{key:"deeppurple-amber",label:"Deep Purple & Amber",type:"light",primaryColor:"#6750A4"},{key:"indigo-pink",label:"Indigo & Pink",type:"light",primaryColor:"#3F51B5"},{key:"magenta-violet",label:"Magenta & Violet",type:"light",primaryColor:"#D81B60"},{key:"rose-red",label:"Rose & Red",type:"light",primaryColor:"#E91E63"},{key:"pink-bluegrey",label:"Pink & Bluegrey",type:"dark",primaryColor:"#E91E63"},{key:"purple-green",label:"Purple & Green",type:"dark",primaryColor:"#7E57C2"},{key:"azure-blue",label:"Azure & Blue",type:"dark",primaryColor:"#0078D4"},{key:"cyan-orange",label:"Cyan & Orange",type:"dark",primaryColor:"#00B7C3"}];availableMapBackgrounds=[{key:"auto",label:"Follow global theme",background:"",textColor:"",type:"light"},{key:"light-1",label:"Cyan Sky",background:"radial-gradient(ellipse at 20% 20%, #B2EBF2 0%, #E0F7FA 70%)",textColor:"#006064",type:"light"},{key:"light-2",label:"Blue Sky",background:"radial-gradient(ellipse at 20% 20%, #BBDEFB 0%, #E3F2FD 70%)",textColor:"#1565C0",type:"light"},{key:"light-3",label:"Cloud Gray",background:"radial-gradient(ellipse at 20% 20%, #F5F5F5 0%, #FAFAFA 70%)",textColor:"#424242",type:"light"},{key:"light-4",label:"Lavender",background:"radial-gradient(ellipse at 20% 20%, #E1BEE7 0%, #F3E5F5 70%)",textColor:"#4A148C",type:"light"},{key:"dark-1",label:"Deep Cyan",background:"linear-gradient(135deg, #006064 0%, #00838F 50%, #006064 100%)",textColor:"#FFFFFF",type:"dark"},{key:"dark-2",label:"Deep Blue",background:"linear-gradient(135deg, #1565C0 0%, #1976D2 50%, #1565C0 100%)",textColor:"#FFFFFF",type:"dark"},{key:"dark-3",label:"Charcoal",background:"linear-gradient(135deg, #424242 0%, #616161 50%, #424242 100%)",textColor:"#FFFFFF",type:"dark"},{key:"dark-4",label:"Deep Purple",background:"linear-gradient(135deg, #4A148C 0%, #6A1B9A 50%, #4A148C 100%)",textColor:"#FFFFFF",type:"dark"}];constructor(e,t,n){this.document=e,this.userPreferences=n;let a=localStorage.getItem("theme");this.currentTheme=a||t,this.savedTheme=this.currentTheme;let o=localStorage.getItem("mapTheme");this.currentMapTheme=o||"auto",this.savedMapTheme=this.currentMapTheme,this.applyTheme(this.currentTheme),this.userPreferences.onExternalUpdate(()=>this.applyExternalPreferences())}applyExternalPreferences(){let e=localStorage.getItem("theme");e&&this.availableThemes.some(n=>n.key===e)&&e!==this.currentTheme&&(this.currentTheme=e,this.savedTheme=e,this.applyTheme(e),this.themeChanged.emit(e),this._darkMode$.next(this.isDarkTheme(e)));let t=localStorage.getItem("mapTheme");t&&t!==this.currentMapTheme&&(this.currentMapTheme=t,this.savedMapTheme=t,this.mapThemeChanged.emit(this.getActualMapTheme()))}getCurrentTheme(){return this.currentTheme}getThemeType(){return this.isDarkTheme(this.currentTheme)?"dark":"light"}getActualMapTheme(){if(this.savedMapTheme==="auto")return this.getThemeType();let e=this.availableMapBackgrounds.find(t=>t.key===this.savedMapTheme);return e?e.type:"light"}getActualTheme(){return this.getThemeType()}isDarkTheme(e){return e==="pink-bluegrey"||e==="purple-green"||e==="azure-blue"||e==="cyan-orange"}setTheme(e){this.currentTheme!==e&&(this.currentTheme=e,this.savedTheme=e,this.applyTheme(e),this.saveThemePreference(e),this.themeChanged.emit(e),this.currentMapTheme==="auto"&&this.mapThemeChanged.emit(e),this._darkMode$.next(this.isDarkTheme(e)))}toggleTheme(){let e=this.getThemeType(),t;e==="dark"?t=this.availableThemes.find(n=>n.type==="light")?.key||"deeppurple-amber":t=this.availableThemes.find(n=>n.type==="dark")?.key||"pink-bluegrey",this.setTheme(t)}setDarkMode(e){let t=e?"pink-bluegrey":"indigo-pink";this.setTheme(t)}setMapTheme(e){this.currentMapTheme=e,this.savedMapTheme=e,this.userPreferences.setItem("mapTheme",e),this.mapThemeChanged.emit(this.getActualMapTheme())}restoreTheme(){let e=localStorage.getItem("theme");e&&this.availableThemes.some(t=>t.key===e)&&this.setTheme(e)}applyTheme(e){let t=this.document.documentElement;t.classList.remove("theme-deeppurple-amber","theme-indigo-pink","theme-magenta-violet","theme-rose-red","theme-pink-bluegrey","theme-purple-green","theme-azure-blue","theme-cyan-orange"),t.classList.add(`theme-${e}`)}saveThemePreference(e){this.userPreferences.setItem("theme",e)}isDarkMode(){return this.isDarkTheme(this.currentTheme)}isLightMode(){return!this.isDarkTheme(this.currentTheme)}getCanvasLabelColor(){return this.getActualMapTheme()==="dark"?"#FFFFFF":"#000000"}getCanvasLinkColor(){return this.getActualMapTheme()==="dark"?"#FFFFFF":"#000000"}static \u0275fac=function(t){return new(t||i)(X(ye),X(or),X(ft))};static \u0275prov=V({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})();var ea=(()=>{class i{themeService;userPreferences;symbolScalingSubject=new _;isScrollDisabled=new _;isMapLocked=new _;isTopologySummaryVisible=!0;isLogConsoleVisible=!1;isLayerNumberVisible=!1;isItemLockStatusVisible=!1;logConsoleSubject=new _;mapRenderedEmitter=new p;openReadme;showInterfaceLabels=!0;integrateLinkLabelsToLinks=!0;openConsolesInWidget=!1;defaultSceneWidth;defaultSceneHeight;defaultGridSize;defaultDrawingGridSize;defaultShowGrid;defaultSnapToGrid;defaultLabelStyle;defaultNoteStyle;defaultLinkStyle;static FONT_FAMILIES=["TypeWriter","Noto Sans","Arial","Courier New","Times New Roman","Helvetica","Verdana","Georgia","Comic Sans MS"];static FONT_WEIGHTS=["normal","bold"];static LINK_STYLE_NAMES=["Invisible","Solid","Dash","Dot","Dash Dot","Dash Dot Dot"];static LINK_TYPES=[{label:"Straight",value:"straight"},{label:"Bezier",value:"bezier"},{label:"Flowchart",value:"flowchart"},{label:"StateMachine",value:"statemachine"},{label:"Freeform",value:"freeform"}];static DEFAULT_SCENE_WIDTH=2e3;static DEFAULT_SCENE_HEIGHT=1e3;static DEFAULT_GRID_SIZE=75;static DEFAULT_DRAWING_GRID_SIZE=25;static DEFAULT_SHOW_GRID=!1;static DEFAULT_SNAP_TO_GRID=!1;defaultLabelStyleFallback;defaultNoteStyleFallback;defaultLinkStyleFallback;static SCENE_WIDTH_KEY="defaultSceneWidth";static SCENE_HEIGHT_KEY="defaultSceneHeight";static GRID_SIZE_KEY="defaultGridSize";static DRAWING_GRID_SIZE_KEY="defaultDrawingGridSize";static SHOW_GRID_KEY="defaultShowGrid";static SNAP_TO_GRID_KEY="defaultSnapToGrid";static LABEL_STYLE_KEY="defaultLabelStyle";static NOTE_STYLE_KEY="defaultNoteStyle";static LINK_STYLE_KEY="defaultLinkStyle";constructor(e,t){this.themeService=e,this.userPreferences=t,this.defaultLabelStyleFallback={fontFamily:"TypeWriter",fontSize:10,fontWeight:"bold",color:this.themeService.getCanvasLabelColor()},this.defaultNoteStyleFallback={fontFamily:"Noto Sans",fontSize:11,fontWeight:"bold",color:this.themeService.getCanvasLabelColor()},this.defaultLinkStyleFallback={color:this.themeService.getCanvasLinkColor(),width:2,type:1,link_type:"straight"},this.loadFromStorage(),this.userPreferences.onExternalUpdate(()=>this.loadFromStorage())}loadFromStorage(){this.isLayerNumberVisible=localStorage.getItem("layersVisibility")==="true",localStorage.getItem("integrateLinkLabelsToLinks")?this.integrateLinkLabelsToLinks=localStorage.getItem("integrateLinkLabelsToLinks")==="true":(this.integrateLinkLabelsToLinks=!0,this.userPreferences.setItem("integrateLinkLabelsToLinks","true")),localStorage.getItem("openConsolesInWidget")?this.openConsolesInWidget=localStorage.getItem("openConsolesInWidget")==="true":(this.openConsolesInWidget=!1,this.userPreferences.setItem("openConsolesInWidget","false")),localStorage.getItem("symbolScaling")||this.userPreferences.setItem("symbolScaling","true"),localStorage.getItem("openReadme")?this.openReadme=localStorage.getItem("openReadme")==="true":this.userPreferences.setItem("openReadme","false"),localStorage.getItem("showInterfaceLabels")?this.showInterfaceLabels=localStorage.getItem("showInterfaceLabels")==="true":this.userPreferences.setItem("showInterfaceLabels","true"),this.defaultSceneWidth=this.readNumber(i.SCENE_WIDTH_KEY,i.DEFAULT_SCENE_WIDTH),this.defaultSceneHeight=this.readNumber(i.SCENE_HEIGHT_KEY,i.DEFAULT_SCENE_HEIGHT),this.defaultGridSize=this.readNumber(i.GRID_SIZE_KEY,i.DEFAULT_GRID_SIZE),this.defaultDrawingGridSize=this.readNumber(i.DRAWING_GRID_SIZE_KEY,i.DEFAULT_DRAWING_GRID_SIZE),this.defaultShowGrid=this.readBoolean(i.SHOW_GRID_KEY,i.DEFAULT_SHOW_GRID),this.defaultSnapToGrid=this.readBoolean(i.SNAP_TO_GRID_KEY,i.DEFAULT_SNAP_TO_GRID),this.defaultLabelStyle=this.readTextStyle(i.LABEL_STYLE_KEY,this.defaultLabelStyleFallback),this.defaultNoteStyle=this.readTextStyle(i.NOTE_STYLE_KEY,this.defaultNoteStyleFallback),this.defaultLinkStyle=this.readLinkStyle(i.LINK_STYLE_KEY,this.defaultLinkStyleFallback)}readNumber(e,t){let n=localStorage.getItem(e);if(n===null)return t;let a=parseInt(n,10);return Number.isFinite(a)&&a>=0?a:t}readBoolean(e,t){let n=localStorage.getItem(e);return n===null?t:n==="true"}readTextStyle(e,t){let n=localStorage.getItem(e);if(!n)return j({},t);try{return this.normalizeTextStyle(JSON.parse(n),t)}catch{return j({},t)}}readLinkStyle(e,t){let n=localStorage.getItem(e);if(!n)return j({},t);try{return this.normalizeLinkStyle(JSON.parse(n),t)}catch{return j({},t)}}normalizeTextStyle(e,t){let n=typeof e=="object"&&e!==null?e:{},a=Number(n.fontSize);return{fontFamily:i.FONT_FAMILIES.includes(n.fontFamily)?n.fontFamily:t.fontFamily,fontSize:Number.isFinite(a)?Math.min(200,Math.max(1,Math.round(a*2)/2)):t.fontSize,fontWeight:i.FONT_WEIGHTS.includes(n.fontWeight)?n.fontWeight:t.fontWeight,color:this.normalizeColor(n.color,t.color)}}normalizeLinkStyle(e,t){let n=typeof e=="object"&&e!==null?e:{},a=Number(n.width),o=Number(n.type),l=i.LINK_TYPES.map(C=>C.value);return{color:this.normalizeColor(n.color,t.color),width:Number.isFinite(a)?Math.min(20,Math.max(1,Math.round(a))):t.width,type:Number.isInteger(o)&&o>=0&&o<i.LINK_STYLE_NAMES.length?o:t.type,link_type:typeof n.link_type=="string"&&l.includes(n.link_type)?n.link_type:t.link_type}}normalizeColor(e,t){return typeof e=="string"&&/^#[0-9a-f]{6}$/i.test(e)?e.toLowerCase():t}getSymbolScaling(){return localStorage.getItem("symbolScaling")==="true"}setSymbolScaling(e){e?this.userPreferences.setItem("symbolScaling","true"):this.userPreferences.setItem("symbolScaling","false"),this.symbolScalingSubject.next(e)}changeMapLockValue(e){this.isMapLocked.next(e)}setConsoleContextMenuAction(e){this.userPreferences.setItem("consoleContextMenu",e)}getConsoleContextMenuAction(){return localStorage.getItem("consoleContextMenu")}toggleTopologySummary(e){this.isTopologySummaryVisible=e}toggleLogConsole(e){this.isLogConsoleVisible=e}toggleLayers(e){this.isLayerNumberVisible=e}toggleItemLockStatus(e){this.isItemLockStatusVisible=e}toggleShowInterfaceLabels(e){this.showInterfaceLabels=e,this.userPreferences.removeItem("showInterfaceLabels"),e?this.userPreferences.setItem("showInterfaceLabels","true"):this.userPreferences.setItem("showInterfaceLabels","false")}toggleIntegrateInterfaceLabels(e){this.integrateLinkLabelsToLinks=e,this.userPreferences.removeItem("integrateLinkLabelsToLinks"),e?this.userPreferences.setItem("integrateLinkLabelsToLinks","true"):this.userPreferences.setItem("integrateLinkLabelsToLinks","false")}toggleOpenReadme(e){this.openReadme=e,this.userPreferences.removeItem("openReadme"),e?this.userPreferences.setItem("openReadme","true"):this.userPreferences.setItem("openReadme","false")}toggleOpenConsolesInWidget(e){this.openConsolesInWidget=e,this.userPreferences.removeItem("openConsolesInWidget"),e?this.userPreferences.setItem("openConsolesInWidget","true"):this.userPreferences.setItem("openConsolesInWidget","false")}getDefaultSceneWidth(){return this.defaultSceneWidth}setDefaultSceneWidth(e){let t=Number.isFinite(e)&&e>=0?Math.round(e):i.DEFAULT_SCENE_WIDTH;this.defaultSceneWidth=t,this.userPreferences.setItem(i.SCENE_WIDTH_KEY,String(t))}getDefaultSceneHeight(){return this.defaultSceneHeight}setDefaultSceneHeight(e){let t=Number.isFinite(e)&&e>=0?Math.round(e):i.DEFAULT_SCENE_HEIGHT;this.defaultSceneHeight=t,this.userPreferences.setItem(i.SCENE_HEIGHT_KEY,String(t))}getDefaultGridSize(){return this.defaultGridSize}setDefaultGridSize(e){let t=Number.isFinite(e)&&e>=0?Math.round(e):i.DEFAULT_GRID_SIZE;this.defaultGridSize=t,this.userPreferences.setItem(i.GRID_SIZE_KEY,String(t))}getDefaultDrawingGridSize(){return this.defaultDrawingGridSize}setDefaultDrawingGridSize(e){let t=Number.isFinite(e)&&e>=0?Math.round(e):i.DEFAULT_DRAWING_GRID_SIZE;this.defaultDrawingGridSize=t,this.userPreferences.setItem(i.DRAWING_GRID_SIZE_KEY,String(t))}getDefaultShowGrid(){return this.defaultShowGrid}setDefaultShowGrid(e){this.defaultShowGrid=e,this.userPreferences.setItem(i.SHOW_GRID_KEY,e?"true":"false")}getDefaultSnapToGrid(){return this.defaultSnapToGrid}setDefaultSnapToGrid(e){this.defaultSnapToGrid=e,this.userPreferences.setItem(i.SNAP_TO_GRID_KEY,e?"true":"false")}getDefaultLabelStyle(){return Fe(j({},this.defaultLabelStyle),{color:this.hasDefaultLabelStyle()?this.defaultLabelStyle.color:this.themeService.getCanvasLabelColor()})}hasDefaultLabelStyle(){return localStorage.getItem(i.LABEL_STYLE_KEY)!==null}setDefaultLabelStyle(e){this.defaultLabelStyle=this.normalizeTextStyle(e,this.defaultLabelStyleFallback),this.userPreferences.setItem(i.LABEL_STYLE_KEY,JSON.stringify(this.defaultLabelStyle))}getDefaultNoteStyle(){return Fe(j({},this.defaultNoteStyle),{color:this.hasDefaultNoteStyle()?this.defaultNoteStyle.color:this.themeService.getCanvasLabelColor()})}hasDefaultNoteStyle(){return localStorage.getItem(i.NOTE_STYLE_KEY)!==null}setDefaultNoteStyle(e){this.defaultNoteStyle=this.normalizeTextStyle(e,this.defaultNoteStyleFallback),this.userPreferences.setItem(i.NOTE_STYLE_KEY,JSON.stringify(this.defaultNoteStyle))}getDefaultLinkStyle(){return Fe(j({},this.defaultLinkStyle),{color:this.hasDefaultLinkStyle()?this.defaultLinkStyle.color:this.themeService.getCanvasLinkColor()})}hasDefaultLinkStyle(){return localStorage.getItem(i.LINK_STYLE_KEY)!==null}setDefaultLinkStyle(e){this.defaultLinkStyle=this.normalizeLinkStyle(e,this.defaultLinkStyleFallback),this.userPreferences.setItem(i.LINK_STYLE_KEY,JSON.stringify(this.defaultLinkStyle))}static \u0275fac=function(t){return new(t||i)(X(Ji),X(ft))};static \u0275prov=V({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})();var zd=(()=>{class i extends Je{getItemKey(e){return e.node_id}static \u0275fac=(()=>{let e;return function(n){return(e||(e=Re(i)))(n||i)}})();static \u0275prov=V({token:i,factory:i.\u0275fac})}return i})();var Yd=(()=>{class i{router;toasterService;mapSettingsService;nodeConsoleTrigger=new p;closeNodeConsoleTrigger=new _;consoleResized=new _;openConsoles=0;defaultConsoleWidth=720;defaultConsoleHeight=408;defaultNumberOfColumns=80;defaultNumberOfRows=24;lastNumberOfColumns;lastNumberOfRows;constructor(e,t,n){this.router=e,this.toasterService=t,this.mapSettingsService=n}getNumberOfColumns(){return this.lastNumberOfColumns}getNumberOfRows(){return this.lastNumberOfRows}setNumberOfColumns(e){this.lastNumberOfColumns=e}setNumberOfRows(e){this.lastNumberOfRows=e}openConsoleForNode(e){this.nodeConsoleTrigger.emit(e)}closeConsoleForNode(e){this.closeNodeConsoleTrigger.next(e)}resizeTerminal(e){this.consoleResized.next(e)}getLineWidth(){return this.defaultConsoleWidth/this.defaultNumberOfColumns}getLineHeight(){return this.defaultConsoleHeight/this.defaultNumberOfRows}getUrl(e,t){let n="ws";return e.protocol==="https:"&&(n="wss"),`${n}://${e.host}:${e.port}/${Ke.current_version}/projects/${t.project_id}/nodes/${t.node_id}/console/ws?token=${e.authToken}`}sendTerminalSize(e,t,n){e&&e.readyState===WebSocket.OPEN&&e.send(new Blob([JSON.stringify({cols:t,rows:n})]))}openConsolesForAllNodesInWidget(e){let t="Please start the following nodes if you want to open consoles for them: ",n=0;e.forEach(a=>{a.console_type!=="none"&&(a.status==="started"?(this.mapSettingsService.logConsoleSubject.next(!0),setTimeout(()=>{this.openConsoleForNode(a)},500)):(n++,t+=a.name+" "))}),n>0&&this.toasterService.error(t)}openConsolesForAllNodesInNewTabs(e){let t="Please start the following nodes if you want to open consoles in tabs for them: ",n=0;e.forEach(a=>{if(a.console_type==="telnet"||a.console_type==="ssh"||a.console_type==="docker_exec")if(a.status==="started"){let o=this.router.url.split("/"),l=`/static/web-ui/${o[1]}/${o[2]}/${o[3]}/${o[4]}/nodes/${a.node_id}`;window.open(l)}else n++,t+=a.name+" "}),n>0&&this.toasterService.error(t)}static \u0275fac=function(t){return new(t||i)(X(si),X(ci),X(ea))};static \u0275prov=V({token:i,factory:i.\u0275fac})}return i})();var qd=(()=>{class i{get vertical(){return this._vertical}set vertical(e){this._vertical=Le(e)}_vertical=!1;get inset(){return this._inset}set inset(e){this._inset=Le(e)}_inset=!1;static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["mat-divider"]],hostAttrs:["role","separator",1,"mat-divider"],hostVars:7,hostBindings:function(t,n){t&2&&(T("aria-orientation",n.vertical?"vertical":"horizontal"),g("mat-divider-vertical",n.vertical)("mat-divider-horizontal",!n.vertical)("mat-divider-inset",n.inset))},inputs:{vertical:"vertical",inset:"inset"},decls:0,vars:0,template:function(t,n){},styles:[`.mat-divider {
  display: block;
  margin: 0;
  border-top-style: solid;
  border-top-color: var(--mat-divider-color, var(--mat-sys-outline-variant));
  border-top-width: var(--mat-divider-width, 1px);
}
.mat-divider.mat-divider-vertical {
  border-top: 0;
  border-right-style: solid;
  border-right-color: var(--mat-divider-color, var(--mat-sys-outline-variant));
  border-right-width: var(--mat-divider-width, 1px);
}
.mat-divider.mat-divider-inset {
  margin-left: 80px;
}
[dir=rtl] .mat-divider.mat-divider-inset {
  margin-left: auto;
  margin-right: 80px;
}
`],encapsulation:2,changeDetection:0})}return i})(),Kd=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=A({type:i});static \u0275inj=F({imports:[W]})}return i})();var je=typeof window>"u"?!1:"ontouchstart"in window||navigator.maxTouchPoints>0||navigator.msMaxTouchPoints>0;function lr(i){let s=i.cloneNode(!0),e=s.querySelectorAll("[id]"),t=i.nodeName.toLowerCase();return s.removeAttribute("id"),e.forEach(n=>{n.removeAttribute("id")}),t==="canvas"?ia(i,s):(t==="input"||t==="select"||t==="textarea")&&na(i,s),ta("canvas",i,s,ia),ta("input, textarea, select",i,s,na),s}function ta(i,s,e,t){let n=s.querySelectorAll(i);if(n.length){let a=e.querySelectorAll(i);for(let o=0;o<n.length;o++)t(n[o],a[o])}}var cr=0;function na(i,s){s.type!=="file"&&(s.value=i.value),s.type==="radio"&&s.name&&(s.name=`mat-clone-${s.name}-${cr++}`)}function ia(i,s){let e=s.getContext("2d");if(e)try{e.drawImage(i,0,0)}catch{}}function la(i){return i.type.startsWith("touch")}function aa(i,s,e,t){let n={top:i.top,bottom:i.bottom,left:i.left,right:i.right};return s.top&&(n.top+=t),s.bottom&&(n.bottom+=t),s.left&&(n.left+=e),s.right&&(n.right+=e),n.height=n.bottom-n.top,n.width=n.right-n.left,n}function dr(i,s){let e=0,t=0,n=i.nativeElement.style,o=["transform","-ms-transform","-moz-transform","-o-transform"].map(l=>n[l]).find(l=>!!l);if(o&&o.includes("translate")&&(e=o.replace(/.*translate3?d?\((-?[0-9]*)px, (-?[0-9]*)px.*/,"$1"),t=o.replace(/.*translate3?d?\((-?[0-9]*)px, (-?[0-9]*)px.*/,"$2")),s==="absolute")return{height:i.nativeElement.offsetHeight,width:i.nativeElement.offsetWidth,top:i.nativeElement.offsetTop-t,bottom:i.nativeElement.offsetHeight+i.nativeElement.offsetTop-t,left:i.nativeElement.offsetLeft-e,right:i.nativeElement.offsetWidth+i.nativeElement.offsetLeft-e};{let l=i.nativeElement.getBoundingClientRect();return{height:l.height,width:l.width,top:l.top-t,bottom:l.bottom-t,left:l.left-e,right:l.right-e,scrollTop:i.nativeElement.scrollTop,scrollLeft:i.nativeElement.scrollLeft}}}var oa=Object.freeze({topLeft:"nw-resize",topRight:"ne-resize",bottomLeft:"sw-resize",bottomRight:"se-resize",leftOrRight:"col-resize",topOrBottom:"row-resize"});function ra(i,s){return i.left&&i.top?s.topLeft:i.right&&i.top?s.topRight:i.left&&i.bottom?s.bottomLeft:i.right&&i.bottom?s.bottomRight:i.left||i.right?s.leftOrRight:i.top||i.bottom?s.topOrBottom:""}function Et({edges:i,initialRectangle:s,newRectangle:e}){let t={};return Object.keys(i).forEach(n=>{t[n]=(e[n]||0)-(s[n]||0)}),t}var sa="resize-active",mr="resize-ghost-element",hr=50,ur=(()=>{class i{constructor(){this.enableGhostResize=!1,this.resizeSnapGrid={},this.resizeCursors=oa,this.ghostElementPositioning="fixed",this.allowNegativeResizes=!1,this.mouseMoveThrottleMS=hr,this.resizeStart=new p,this.resizing=new p,this.resizeEnd=new p,this.mouseup=new _,this.mousedown=new _,this.mousemove=new _,this.destroy$=new _,this.platformId=r(Cn),this.renderer=r(te),this.elm=r(I),this.zone=r(B),this.rendererFactory=r(wn),this.document=r(ye),this.pointerEventListeners=ln.getInstance(this.rendererFactory.createRenderer(this.document,null),this.zone)}ngOnInit(){let e=N(this.pointerEventListeners.pointerDown,this.mousedown),t=N(this.pointerEventListeners.pointerMove,this.mousemove).pipe(vn(({event:b})=>{a&&b.cancelable&&!la(b)&&b.preventDefault()}),tt()),n=N(this.pointerEventListeners.pointerUp,this.mouseup),a,o=()=>{a&&a.clonedNode&&(this.elm.nativeElement.parentElement.removeChild(a.clonedNode),this.renderer.setStyle(this.elm.nativeElement,"visibility","inherit"))},l=()=>j(j({},oa),this.resizeCursors);e.pipe(hn(b=>{function Y(S){return{clientX:S.clientX-b.clientX,clientY:S.clientY-b.clientY}}let de=()=>{let S={x:1,y:1};return a&&(this.resizeSnapGrid.left&&a.edges.left?S.x=+this.resizeSnapGrid.left:this.resizeSnapGrid.right&&a.edges.right&&(S.x=+this.resizeSnapGrid.right),this.resizeSnapGrid.top&&a.edges.top?S.y=+this.resizeSnapGrid.top:this.resizeSnapGrid.bottom&&a.edges.bottom&&(S.y=+this.resizeSnapGrid.bottom)),S};function me(S,ne){return{x:Math.ceil(S.clientX/ne.x),y:Math.ceil(S.clientY/ne.y)}}return N(t.pipe(Ge(1)).pipe(he(S=>[,S])),t.pipe(lt())).pipe(he(([S,ne])=>[S&&Y(S),Y(ne)])).pipe(Q(([S,ne])=>{if(!S)return!0;let st=de(),cn=me(S,st),dn=me(ne,st);return cn.x!==dn.x||cn.y!==dn.y})).pipe(he(([,S])=>{let ne=de();return{clientX:Math.round(S.clientX/ne.x)*ne.x,clientY:Math.round(S.clientY/ne.y)*ne.y}})).pipe(y(N(n,e)))})).pipe(Q(()=>!!a)).pipe(he(({clientX:b,clientY:Y})=>aa(a.startingRect,a.edges,b,Y))).pipe(Q(b=>this.allowNegativeResizes||!!(b.height&&b.width&&b.height>0&&b.width>0))).pipe(Q(b=>this.validateResize?this.validateResize({rectangle:b,edges:Et({edges:a.edges,initialRectangle:a.startingRect,newRectangle:b})}):!0),y(this.destroy$)).subscribe(b=>{a&&a.clonedNode&&(this.renderer.setStyle(a.clonedNode,"height",`${b.height}px`),this.renderer.setStyle(a.clonedNode,"width",`${b.width}px`),this.renderer.setStyle(a.clonedNode,"top",`${b.top}px`),this.renderer.setStyle(a.clonedNode,"left",`${b.left}px`)),this.resizing.observers.length>0&&this.zone.run(()=>{this.resizing.emit({edges:Et({edges:a.edges,initialRectangle:a.startingRect,newRectangle:b}),rectangle:b})}),a.currentRect=b}),e.pipe(he(({edges:b})=>b||{}),Q(b=>Object.keys(b).length>0),y(this.destroy$)).subscribe(b=>{a&&o();let Y=dr(this.elm,this.ghostElementPositioning);a={edges:b,startingRect:Y,currentRect:Y};let de=l(),me=ra(a.edges,de);this.renderer.setStyle(document.body,"cursor",me),this.setElementClass(this.elm,sa,!0),this.enableGhostResize&&(a.clonedNode=lr(this.elm.nativeElement),this.elm.nativeElement.parentElement.appendChild(a.clonedNode),this.renderer.setStyle(this.elm.nativeElement,"visibility","hidden"),this.renderer.setStyle(a.clonedNode,"position",this.ghostElementPositioning),this.renderer.setStyle(a.clonedNode,"left",`${a.startingRect.left}px`),this.renderer.setStyle(a.clonedNode,"top",`${a.startingRect.top}px`),this.renderer.setStyle(a.clonedNode,"height",`${a.startingRect.height}px`),this.renderer.setStyle(a.clonedNode,"width",`${a.startingRect.width}px`),this.renderer.setStyle(a.clonedNode,"cursor",ra(a.edges,de)),this.renderer.addClass(a.clonedNode,mr),a.clonedNode.scrollTop=a.startingRect.scrollTop,a.clonedNode.scrollLeft=a.startingRect.scrollLeft),this.resizeStart.observers.length>0&&this.zone.run(()=>{this.resizeStart.emit({edges:Et({edges:b,initialRectangle:Y,newRectangle:Y}),rectangle:aa(Y,{},0,0)})})}),n.pipe(y(this.destroy$)).subscribe(()=>{a&&(this.renderer.removeClass(this.elm.nativeElement,sa),this.renderer.setStyle(document.body,"cursor",""),this.renderer.setStyle(this.elm.nativeElement,"cursor",""),this.resizeEnd.observers.length>0&&this.zone.run(()=>{this.resizeEnd.emit({edges:Et({edges:a.edges,initialRectangle:a.startingRect,newRectangle:a.currentRect}),rectangle:a.currentRect})}),o(),a=null)})}ngOnDestroy(){An(this.platformId)&&this.renderer.setStyle(document.body,"cursor",""),this.mousedown.complete(),this.mouseup.complete(),this.mousemove.complete(),this.destroy$.next()}setElementClass(e,t,n){n?this.renderer.addClass(e.nativeElement,t):this.renderer.removeClass(e.nativeElement,t)}static{this.\u0275fac=function(t){return new(t||i)}}static{this.\u0275dir=E({type:i,selectors:[["","mwlResizable",""]],inputs:{validateResize:"validateResize",enableGhostResize:"enableGhostResize",resizeSnapGrid:"resizeSnapGrid",resizeCursors:"resizeCursors",ghostElementPositioning:"ghostElementPositioning",allowNegativeResizes:"allowNegativeResizes",mouseMoveThrottleMS:"mouseMoveThrottleMS"},outputs:{resizeStart:"resizeStart",resizing:"resizing",resizeEnd:"resizeEnd"},exportAs:["mwlResizable"]})}}return i})(),ln=class i{static getInstance(s,e){return i.instance||(i.instance=new i(s,e)),i.instance}constructor(s,e){this.pointerDown=new Se(t=>{let n,a;return e.runOutsideAngular(()=>{n=s.listen("document","mousedown",o=>{t.next({clientX:o.clientX,clientY:o.clientY,event:o})}),je&&(a=s.listen("document","touchstart",o=>{t.next({clientX:o.touches[0].clientX,clientY:o.touches[0].clientY,event:o})}))}),()=>{n(),je&&a()}}).pipe(tt()),this.pointerMove=new Se(t=>{let n,a;return e.runOutsideAngular(()=>{n=s.listen("document","mousemove",o=>{t.next({clientX:o.clientX,clientY:o.clientY,event:o})}),je&&(a=s.listen("document","touchmove",o=>{t.next({clientX:o.targetTouches[0].clientX,clientY:o.targetTouches[0].clientY,event:o})}))}),()=>{n(),je&&a()}}).pipe(tt()),this.pointerUp=new Se(t=>{let n,a,o;return e.runOutsideAngular(()=>{n=s.listen("document","mouseup",l=>{t.next({clientX:l.clientX,clientY:l.clientY,event:l})}),je&&(a=s.listen("document","touchend",l=>{t.next({clientX:l.changedTouches[0].clientX,clientY:l.changedTouches[0].clientY,event:l})}),o=s.listen("document","touchcancel",l=>{t.next({clientX:l.changedTouches[0].clientX,clientY:l.changedTouches[0].clientY,event:l})}))}),()=>{n(),je&&(a(),o())}}).pipe(tt())}},ca=(()=>{class i{constructor(){this.renderer=r(te),this.element=r(I),this.zone=r(B),this.resizableDirective=r(ur,{optional:!0}),this.resizeEdges={},this.eventListeners={},this.destroy$=new _}ngOnInit(){this.zone.runOutsideAngular(()=>{this.listenOnTheHost("mousedown").subscribe(e=>{this.onMousedown(e,e.clientX,e.clientY)}),this.listenOnTheHost("mouseup").subscribe(e=>{this.onMouseup(e.clientX,e.clientY)}),je&&(this.listenOnTheHost("touchstart").subscribe(e=>{this.onMousedown(e,e.touches[0].clientX,e.touches[0].clientY)}),N(this.listenOnTheHost("touchend"),this.listenOnTheHost("touchcancel")).subscribe(e=>{this.onMouseup(e.changedTouches[0].clientX,e.changedTouches[0].clientY)}))})}ngOnDestroy(){this.destroy$.next(),this.unsubscribeEventListeners()}onMousedown(e,t,n){e.cancelable&&!la(e)&&e.preventDefault(),this.eventListeners.touchmove||(this.eventListeners.touchmove=this.renderer.listen(this.element.nativeElement,"touchmove",a=>{this.onMousemove(a,a.targetTouches[0].clientX,a.targetTouches[0].clientY)})),this.eventListeners.mousemove||(this.eventListeners.mousemove=this.renderer.listen(this.element.nativeElement,"mousemove",a=>{this.onMousemove(a,a.clientX,a.clientY)})),this.resizable.mousedown.next({clientX:t,clientY:n,edges:this.resizeEdges})}onMouseup(e,t){this.unsubscribeEventListeners(),this.resizable.mouseup.next({clientX:e,clientY:t,edges:this.resizeEdges})}get resizable(){return this.resizableDirective||this.resizableContainer}onMousemove(e,t,n){this.resizable.mousemove.next({clientX:t,clientY:n,edges:this.resizeEdges,event:e})}unsubscribeEventListeners(){Object.keys(this.eventListeners).forEach(e=>{this.eventListeners[e](),delete this.eventListeners[e]})}listenOnTheHost(e){return pn(this.element.nativeElement,e).pipe(y(this.destroy$))}static{this.\u0275fac=function(t){return new(t||i)}}static{this.\u0275dir=E({type:i,selectors:[["","mwlResizeHandle",""]],inputs:{resizeEdges:"resizeEdges",resizableContainer:"resizableContainer"}})}}return i})(),rm=(()=>{class i{static{this.\u0275fac=function(t){return new(t||i)}}static{this.\u0275mod=A({type:i})}static{this.\u0275inj=F({})}}return i})();var pr=()=>({top:!0}),fr=()=>({right:!0}),br=()=>({bottom:!0}),_r=()=>({left:!0}),gr=()=>({top:!0,left:!0}),vr=()=>({top:!0,right:!0}),yr=()=>({bottom:!0,left:!0}),xr=()=>({bottom:!0,right:!0}),um=(()=>{class i{prefix=On("gns3-window");baseClass=Pe(()=>`${this.prefix()}__resize-handle`);handleClass(e){let t=this.baseClass();return`${t} ${t}--${e}`}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=D({type:i,selectors:[["app-floating-window-resize-handles"]],inputs:{prefix:[1,"prefix"]},decls:8,vars:32,consts:[["mwlResizeHandle","",3,"resizeEdges"]],template:function(t,n){t&1&&R(0,"div",0)(1,"div",0)(2,"div",0)(3,"div",0)(4,"div",0)(5,"div",0)(6,"div",0)(7,"div",0),t&2&&(H(n.handleClass("top")),v("resizeEdges",Te(24,pr)),c(),H(n.handleClass("right")),v("resizeEdges",Te(25,fr)),c(),H(n.handleClass("bottom")),v("resizeEdges",Te(26,br)),c(),H(n.handleClass("left")),v("resizeEdges",Te(27,_r)),c(),H(n.handleClass("top-left")),v("resizeEdges",Te(28,gr)),c(),H(n.handleClass("top-right")),v("resizeEdges",Te(29,vr)),c(),H(n.handleClass("bottom-left")),v("resizeEdges",Te(30,yr)),c(),H(n.handleClass("bottom-right")),v("resizeEdges",Te(31,xr)))},dependencies:[ca],styles:["[_nghost-%COMP%]{display:contents}.gns3-window__resize-handle[_ngcontent-%COMP%]{position:absolute;z-index:100;background:transparent}.gns3-window__resize-handle--top[_ngcontent-%COMP%]{top:-10px;left:0;right:0;height:10px;cursor:ns-resize}.gns3-window__resize-handle--right[_ngcontent-%COMP%]{top:0;right:-10px;bottom:0;width:10px;cursor:ew-resize}.gns3-window__resize-handle--bottom[_ngcontent-%COMP%]{bottom:-10px;left:0;right:0;height:10px;cursor:ns-resize}.gns3-window__resize-handle--left[_ngcontent-%COMP%]{top:0;left:-10px;bottom:0;width:10px;cursor:ew-resize}.gns3-window__resize-handle--top-left[_ngcontent-%COMP%]{top:-10px;left:-10px;width:16px;height:16px;cursor:nwse-resize}.gns3-window__resize-handle--top-right[_ngcontent-%COMP%]{top:-10px;right:-10px;width:16px;height:16px;cursor:nesw-resize}.gns3-window__resize-handle--bottom-left[_ngcontent-%COMP%]{bottom:-10px;left:-10px;width:16px;height:16px;cursor:nesw-resize}.gns3-window__resize-handle--bottom-right[_ngcontent-%COMP%]{bottom:-10px;right:-10px;width:16px;height:16px;cursor:nwse-resize}.gns3-replay__resize-handle[_ngcontent-%COMP%]{position:absolute;z-index:100;background:transparent}.gns3-replay__resize-handle--top[_ngcontent-%COMP%]{top:-10px;left:0;right:0;height:10px;cursor:ns-resize}.gns3-replay__resize-handle--right[_ngcontent-%COMP%]{top:0;right:-10px;bottom:0;width:10px;cursor:ew-resize}.gns3-replay__resize-handle--bottom[_ngcontent-%COMP%]{bottom:-10px;left:0;right:0;height:10px;cursor:ns-resize}.gns3-replay__resize-handle--left[_ngcontent-%COMP%]{top:0;left:-10px;bottom:0;width:10px;cursor:ew-resize}.gns3-replay__resize-handle--top-left[_ngcontent-%COMP%]{top:-10px;left:-10px;width:16px;height:16px;cursor:nwse-resize}.gns3-replay__resize-handle--top-right[_ngcontent-%COMP%]{top:-10px;right:-10px;width:16px;height:16px;cursor:nesw-resize}.gns3-replay__resize-handle--bottom-left[_ngcontent-%COMP%]{bottom:-10px;left:-10px;width:16px;height:16px;cursor:nesw-resize}.gns3-replay__resize-handle--bottom-right[_ngcontent-%COMP%]{bottom:-10px;right:-10px;width:16px;height:16px;cursor:nwse-resize}.gns3-window--resizing[_nghost-%COMP%]   .gns3-window__resize-handle[_ngcontent-%COMP%], .gns3-window--resizing   [_nghost-%COMP%]   .gns3-window__resize-handle[_ngcontent-%COMP%], .gns3-replay__window--resizing[_nghost-%COMP%]   .gns3-replay__resize-handle[_ngcontent-%COMP%], .gns3-replay__window--resizing   [_nghost-%COMP%]   .gns3-replay__resize-handle[_ngcontent-%COMP%], .gns3-replay__main--resizing[_nghost-%COMP%]   .gns3-replay__resize-handle[_ngcontent-%COMP%], .gns3-replay__main--resizing   [_nghost-%COMP%]   .gns3-replay__resize-handle[_ngcontent-%COMP%]{background:transparent}@media(max-width:720px){.topology-inspector[_nghost-%COMP%]   .gns3-window__resize-handle[_ngcontent-%COMP%], .topology-inspector   [_nghost-%COMP%]   .gns3-window__resize-handle[_ngcontent-%COMP%]{display:none}}"],changeDetection:0})}return i})();function fm(i,s,e){let t=Math.max(0,s.width-i.width),n=Math.max(e,s.height-i.height);return{left:Math.min(Math.max(i.left,0),t),top:Math.min(Math.max(i.top,e),n),width:i.width,height:i.height}}var kr=32,Cr=96;function bm(i,s,e,t,n){return{width:Math.min(Math.max(i,t),Math.max(e.width-kr,t)),height:Math.min(Math.max(s,n),Math.max(e.height-Cr,n))}}var ym=(()=>{class i{_entries=Z([]);entries=this._entries.asReadonly();getSnapshot(){return this._entries()}rebuildAll(e){let t=[];for(let n of e)this.collect(n,t);this.setEntries(t)}rebuildFromAggregate(e){let t=[];for(let[n,a]of Object.entries(e)){let o=n.indexOf("/"),l=o>=0?n.slice(o+1):n;t.push({name:l,linkId:a.link_id,bpf:a.bpf,tag:a.tag??null,color:a.color})}this.setEntries(t)}reconcileLink(e){let t=this._entries().filter(n=>n.linkId!==e.link_id);this.collect(e,t),this.setEntries(t)}removeLink(e){let t=this._entries().filter(n=>n.linkId!==e);this.setEntries(t)}reset(){this._entries.set([])}collect(e,t){if(e.markers)for(let[n,a]of Object.entries(e.markers))t.push({name:n,linkId:e.link_id,bpf:a.bpf,tag:a.tag,color:a.color})}setEntries(e){wr(this._entries(),e)||this._entries.set(e)}static \u0275fac=function(t){return new(t||i)};static \u0275prov=V({token:i,factory:i.\u0275fac})}return i})();function wr(i,s){if(i.length!==s.length)return!1;let e=n=>`${n.linkId}\0${n.name}\0${n.bpf}\0${n.tag??""}\0${n.color??""}`,t=new Set(i.map(e));for(let n of s)if(!t.has(e(n)))return!1;return!0}export{va as a,Kr as b,Ut as c,Cs as d,_t as e,ws as f,Ts as g,Xt as h,so as i,Zt as j,lo as k,co as l,Jt as m,en as n,Pi as o,Fi as p,Li as q,Dt as r,kt as s,Ct as t,za as u,qt as v,wt as w,bi as x,_i as y,gi as z,Tt as A,nc as B,ic as C,ac as D,Ni as E,zi as F,hc as G,Lo as H,Rc as I,Lc as J,Ji as K,qo as L,Xo as M,Zo as N,gd as O,nr as P,ir as Q,vd as R,yd as S,Je as T,Td as U,ea as V,zd as W,ym as X,Yd as Y,qd as Z,Kd as _,ur as $,rm as aa,um as ba,fm as ca,kr as da,Cr as ea,bm as fa};
