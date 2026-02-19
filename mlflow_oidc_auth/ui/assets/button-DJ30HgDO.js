var e=Object.create,t=Object.defineProperty,n=Object.getOwnPropertyDescriptor,r=Object.getOwnPropertyNames,i=Object.getPrototypeOf,a=Object.prototype.hasOwnProperty,o=(e,t)=>()=>(t||e((t={exports:{}}).exports,t),t.exports),s=(e,i,o,s)=>{if(i&&typeof i==`object`||typeof i==`function`)for(var c=r(i),l=0,u=c.length,d;l<u;l++)d=c[l],!a.call(e,d)&&d!==o&&t(e,d,{get:(e=>i[e]).bind(null,d),enumerable:!(s=n(i,d))||s.enumerable});return e},c=(n,r,a)=>(a=n==null?{}:e(i(n)),s(r||!n||!n.__esModule?t(a,`default`,{value:n,enumerable:!0}):a,n)),l=o((e=>{var t=Symbol.for(`react.transitional.element`),n=Symbol.for(`react.portal`),r=Symbol.for(`react.fragment`),i=Symbol.for(`react.strict_mode`),a=Symbol.for(`react.profiler`),o=Symbol.for(`react.consumer`),s=Symbol.for(`react.context`),c=Symbol.for(`react.forward_ref`),l=Symbol.for(`react.suspense`),u=Symbol.for(`react.memo`),d=Symbol.for(`react.lazy`),f=Symbol.for(`react.activity`),p=Symbol.iterator;function m(e){return typeof e!=`object`||!e?null:(e=p&&e[p]||e[`@@iterator`],typeof e==`function`?e:null)}var h={isMounted:function(){return!1},enqueueForceUpdate:function(){},enqueueReplaceState:function(){},enqueueSetState:function(){}},g=Object.assign,_={};function v(e,t,n){this.props=e,this.context=t,this.refs=_,this.updater=n||h}v.prototype.isReactComponent={},v.prototype.setState=function(e,t){if(typeof e!=`object`&&typeof e!=`function`&&e!=null)throw Error(`takes an object of state variables to update or a function which returns an object of state variables.`);this.updater.enqueueSetState(this,e,t,`setState`)},v.prototype.forceUpdate=function(e){this.updater.enqueueForceUpdate(this,e,`forceUpdate`)};function y(){}y.prototype=v.prototype;function b(e,t,n){this.props=e,this.context=t,this.refs=_,this.updater=n||h}var x=b.prototype=new y;x.constructor=b,g(x,v.prototype),x.isPureReactComponent=!0;var ee=Array.isArray;function te(){}var S={H:null,A:null,T:null,S:null},ne=Object.prototype.hasOwnProperty;function C(e,n,r){var i=r.ref;return{$$typeof:t,type:e,key:n,ref:i===void 0?null:i,props:r}}function re(e,t){return C(e.type,t,e.props)}function w(e){return typeof e==`object`&&!!e&&e.$$typeof===t}function ie(e){var t={"=":`=0`,":":`=2`};return`$`+e.replace(/[=:]/g,function(e){return t[e]})}var ae=/\/+/g;function T(e,t){return typeof e==`object`&&e&&e.key!=null?ie(``+e.key):t.toString(36)}function oe(e){switch(e.status){case`fulfilled`:return e.value;case`rejected`:throw e.reason;default:switch(typeof e.status==`string`?e.then(te,te):(e.status=`pending`,e.then(function(t){e.status===`pending`&&(e.status=`fulfilled`,e.value=t)},function(t){e.status===`pending`&&(e.status=`rejected`,e.reason=t)})),e.status){case`fulfilled`:return e.value;case`rejected`:throw e.reason}}throw e}function E(e,r,i,a,o){var s=typeof e;(s===`undefined`||s===`boolean`)&&(e=null);var c=!1;if(e===null)c=!0;else switch(s){case`bigint`:case`string`:case`number`:c=!0;break;case`object`:switch(e.$$typeof){case t:case n:c=!0;break;case d:return c=e._init,E(c(e._payload),r,i,a,o)}}if(c)return o=o(e),c=a===``?`.`+T(e,0):a,ee(o)?(i=``,c!=null&&(i=c.replace(ae,`$&/`)+`/`),E(o,r,i,``,function(e){return e})):o!=null&&(w(o)&&(o=re(o,i+(o.key==null||e&&e.key===o.key?``:(``+o.key).replace(ae,`$&/`)+`/`)+c)),r.push(o)),1;c=0;var l=a===``?`.`:a+`:`;if(ee(e))for(var u=0;u<e.length;u++)a=e[u],s=l+T(a,u),c+=E(a,r,i,s,o);else if(u=m(e),typeof u==`function`)for(e=u.call(e),u=0;!(a=e.next()).done;)a=a.value,s=l+T(a,u++),c+=E(a,r,i,s,o);else if(s===`object`){if(typeof e.then==`function`)return E(oe(e),r,i,a,o);throw r=String(e),Error(`Objects are not valid as a React child (found: `+(r===`[object Object]`?`object with keys {`+Object.keys(e).join(`, `)+`}`:r)+`). If you meant to render a collection of children, use an array instead.`)}return c}function D(e,t,n){if(e==null)return e;var r=[],i=0;return E(e,r,``,``,function(e){return t.call(n,e,i++)}),r}function se(e){if(e._status===-1){var t=e._result;t=t(),t.then(function(t){(e._status===0||e._status===-1)&&(e._status=1,e._result=t)},function(t){(e._status===0||e._status===-1)&&(e._status=2,e._result=t)}),e._status===-1&&(e._status=0,e._result=t)}if(e._status===1)return e._result.default;throw e._result}var ce=typeof reportError==`function`?reportError:function(e){if(typeof window==`object`&&typeof window.ErrorEvent==`function`){var t=new window.ErrorEvent(`error`,{bubbles:!0,cancelable:!0,message:typeof e==`object`&&e&&typeof e.message==`string`?String(e.message):String(e),error:e});if(!window.dispatchEvent(t))return}else if(typeof process==`object`&&typeof process.emit==`function`){process.emit(`uncaughtException`,e);return}console.error(e)},le={map:D,forEach:function(e,t,n){D(e,function(){t.apply(this,arguments)},n)},count:function(e){var t=0;return D(e,function(){t++}),t},toArray:function(e){return D(e,function(e){return e})||[]},only:function(e){if(!w(e))throw Error(`React.Children.only expected to receive a single React element child.`);return e}};e.Activity=f,e.Children=le,e.Component=v,e.Fragment=r,e.Profiler=a,e.PureComponent=b,e.StrictMode=i,e.Suspense=l,e.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE=S,e.__COMPILER_RUNTIME={__proto__:null,c:function(e){return S.H.useMemoCache(e)}},e.cache=function(e){return function(){return e.apply(null,arguments)}},e.cacheSignal=function(){return null},e.cloneElement=function(e,t,n){if(e==null)throw Error(`The argument must be a React element, but you passed `+e+`.`);var r=g({},e.props),i=e.key;if(t!=null)for(a in t.key!==void 0&&(i=``+t.key),t)!ne.call(t,a)||a===`key`||a===`__self`||a===`__source`||a===`ref`&&t.ref===void 0||(r[a]=t[a]);var a=arguments.length-2;if(a===1)r.children=n;else if(1<a){for(var o=Array(a),s=0;s<a;s++)o[s]=arguments[s+2];r.children=o}return C(e.type,i,r)},e.createContext=function(e){return e={$$typeof:s,_currentValue:e,_currentValue2:e,_threadCount:0,Provider:null,Consumer:null},e.Provider=e,e.Consumer={$$typeof:o,_context:e},e},e.createElement=function(e,t,n){var r,i={},a=null;if(t!=null)for(r in t.key!==void 0&&(a=``+t.key),t)ne.call(t,r)&&r!==`key`&&r!==`__self`&&r!==`__source`&&(i[r]=t[r]);var o=arguments.length-2;if(o===1)i.children=n;else if(1<o){for(var s=Array(o),c=0;c<o;c++)s[c]=arguments[c+2];i.children=s}if(e&&e.defaultProps)for(r in o=e.defaultProps,o)i[r]===void 0&&(i[r]=o[r]);return C(e,a,i)},e.createRef=function(){return{current:null}},e.forwardRef=function(e){return{$$typeof:c,render:e}},e.isValidElement=w,e.lazy=function(e){return{$$typeof:d,_payload:{_status:-1,_result:e},_init:se}},e.memo=function(e,t){return{$$typeof:u,type:e,compare:t===void 0?null:t}},e.startTransition=function(e){var t=S.T,n={};S.T=n;try{var r=e(),i=S.S;i!==null&&i(n,r),typeof r==`object`&&r&&typeof r.then==`function`&&r.then(te,ce)}catch(e){ce(e)}finally{t!==null&&n.types!==null&&(t.types=n.types),S.T=t}},e.unstable_useCacheRefresh=function(){return S.H.useCacheRefresh()},e.use=function(e){return S.H.use(e)},e.useActionState=function(e,t,n){return S.H.useActionState(e,t,n)},e.useCallback=function(e,t){return S.H.useCallback(e,t)},e.useContext=function(e){return S.H.useContext(e)},e.useDebugValue=function(){},e.useDeferredValue=function(e,t){return S.H.useDeferredValue(e,t)},e.useEffect=function(e,t){return S.H.useEffect(e,t)},e.useEffectEvent=function(e){return S.H.useEffectEvent(e)},e.useId=function(){return S.H.useId()},e.useImperativeHandle=function(e,t,n){return S.H.useImperativeHandle(e,t,n)},e.useInsertionEffect=function(e,t){return S.H.useInsertionEffect(e,t)},e.useLayoutEffect=function(e,t){return S.H.useLayoutEffect(e,t)},e.useMemo=function(e,t){return S.H.useMemo(e,t)},e.useOptimistic=function(e,t){return S.H.useOptimistic(e,t)},e.useReducer=function(e,t,n){return S.H.useReducer(e,t,n)},e.useRef=function(e){return S.H.useRef(e)},e.useState=function(e){return S.H.useState(e)},e.useSyncExternalStore=function(e,t,n){return S.H.useSyncExternalStore(e,t,n)},e.useTransition=function(){return S.H.useTransition()},e.version=`19.2.3`})),u=o(((e,t)=>{t.exports=l()})),d=o((e=>{var t=Symbol.for(`react.transitional.element`),n=Symbol.for(`react.fragment`);function r(e,n,r){var i=null;if(r!==void 0&&(i=``+r),n.key!==void 0&&(i=``+n.key),`key`in n)for(var a in r={},n)a!==`key`&&(r[a]=n[a]);else r=n;return n=r.ref,{$$typeof:t,type:e,key:i,ref:n===void 0?null:n,props:r}}e.Fragment=n,e.jsx=r,e.jsxs=r})),f=o(((e,t)=>{t.exports=d()}));function p(e,t){(t==null||t>e.length)&&(t=e.length);for(var n=0,r=Array(t);n<t;n++)r[n]=e[n];return r}function m(e){if(Array.isArray(e))return e}function h(e){if(Array.isArray(e))return p(e)}function g(e,t){if(!(e instanceof t))throw TypeError(`Cannot call a class as a function`)}function _(e,t){for(var n=0;n<t.length;n++){var r=t[n];r.enumerable=r.enumerable||!1,r.configurable=!0,`value`in r&&(r.writable=!0),Object.defineProperty(e,ae(r.key),r)}}function v(e,t,n){return t&&_(e.prototype,t),n&&_(e,n),Object.defineProperty(e,`prototype`,{writable:!1}),e}function y(e,t){var n=typeof Symbol<`u`&&e[Symbol.iterator]||e[`@@iterator`];if(!n){if(Array.isArray(e)||(n=oe(e))||t&&e&&typeof e.length==`number`){n&&(e=n);var r=0,i=function(){};return{s:i,n:function(){return r>=e.length?{done:!0}:{done:!1,value:e[r++]}},e:function(e){throw e},f:i}}throw TypeError(`Invalid attempt to iterate non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}var a,o=!0,s=!1;return{s:function(){n=n.call(e)},n:function(){var e=n.next();return o=e.done,e},e:function(e){s=!0,a=e},f:function(){try{o||n.return==null||n.return()}finally{if(s)throw a}}}}function b(e,t,n){return(t=ae(t))in e?Object.defineProperty(e,t,{value:n,enumerable:!0,configurable:!0,writable:!0}):e[t]=n,e}function x(e){if(typeof Symbol<`u`&&e[Symbol.iterator]!=null||e[`@@iterator`]!=null)return Array.from(e)}function ee(e,t){var n=e==null?null:typeof Symbol<`u`&&e[Symbol.iterator]||e[`@@iterator`];if(n!=null){var r,i,a,o,s=[],c=!0,l=!1;try{if(a=(n=n.call(e)).next,t===0){if(Object(n)!==n)return;c=!1}else for(;!(c=(r=a.call(n)).done)&&(s.push(r.value),s.length!==t);c=!0);}catch(e){l=!0,i=e}finally{try{if(!c&&n.return!=null&&(o=n.return(),Object(o)!==o))return}finally{if(l)throw i}}return s}}function te(){throw TypeError(`Invalid attempt to destructure non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function S(){throw TypeError(`Invalid attempt to spread non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function ne(e,t){var n=Object.keys(e);if(Object.getOwnPropertySymbols){var r=Object.getOwnPropertySymbols(e);t&&(r=r.filter(function(t){return Object.getOwnPropertyDescriptor(e,t).enumerable})),n.push.apply(n,r)}return n}function C(e){for(var t=1;t<arguments.length;t++){var n=arguments[t]==null?{}:arguments[t];t%2?ne(Object(n),!0).forEach(function(t){b(e,t,n[t])}):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(n)):ne(Object(n)).forEach(function(t){Object.defineProperty(e,t,Object.getOwnPropertyDescriptor(n,t))})}return e}function re(e,t){return m(e)||ee(e,t)||oe(e,t)||te()}function w(e){return h(e)||x(e)||oe(e)||S()}function ie(e,t){if(typeof e!=`object`||!e)return e;var n=e[Symbol.toPrimitive];if(n!==void 0){var r=n.call(e,t||`default`);if(typeof r!=`object`)return r;throw TypeError(`@@toPrimitive must return a primitive value.`)}return(t===`string`?String:Number)(e)}function ae(e){var t=ie(e,`string`);return typeof t==`symbol`?t:t+``}function T(e){"@babel/helpers - typeof";return T=typeof Symbol==`function`&&typeof Symbol.iterator==`symbol`?function(e){return typeof e}:function(e){return e&&typeof Symbol==`function`&&e.constructor===Symbol&&e!==Symbol.prototype?`symbol`:typeof e},T(e)}function oe(e,t){if(e){if(typeof e==`string`)return p(e,t);var n={}.toString.call(e).slice(8,-1);return n===`Object`&&e.constructor&&(n=e.constructor.name),n===`Map`||n===`Set`?Array.from(e):n===`Arguments`||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)?p(e,t):void 0}}var E=function(){},D={},se={},ce=null,le={mark:E,measure:E};try{typeof window<`u`&&(D=window),typeof document<`u`&&(se=document),typeof MutationObserver<`u`&&(ce=MutationObserver),typeof performance<`u`&&(le=performance)}catch{}var ue=(D.navigator||{}).userAgent,de=ue===void 0?``:ue,O=D,k=se,fe=ce,pe=le;O.document;var A=!!k.documentElement&&!!k.head&&typeof k.addEventListener==`function`&&typeof k.createElement==`function`,me=~de.indexOf(`MSIE`)||~de.indexOf(`Trident/`),he,ge=/fa(k|kd|s|r|l|t|d|dr|dl|dt|b|slr|slpr|wsb|tl|ns|nds|es|jr|jfr|jdr|usb|ufsb|udsb|cr|ss|sr|sl|st|sds|sdr|sdl|sdt)?[\-\ ]/,_e=/Font ?Awesome ?([567 ]*)(Solid|Regular|Light|Thin|Duotone|Brands|Free|Pro|Sharp Duotone|Sharp|Kit|Notdog Duo|Notdog|Chisel|Etch|Thumbprint|Jelly Fill|Jelly Duo|Jelly|Utility|Utility Fill|Utility Duo|Slab Press|Slab|Whiteboard)?.*/i,ve={classic:{fa:`solid`,fas:`solid`,"fa-solid":`solid`,far:`regular`,"fa-regular":`regular`,fal:`light`,"fa-light":`light`,fat:`thin`,"fa-thin":`thin`,fab:`brands`,"fa-brands":`brands`},duotone:{fa:`solid`,fad:`solid`,"fa-solid":`solid`,"fa-duotone":`solid`,fadr:`regular`,"fa-regular":`regular`,fadl:`light`,"fa-light":`light`,fadt:`thin`,"fa-thin":`thin`},sharp:{fa:`solid`,fass:`solid`,"fa-solid":`solid`,fasr:`regular`,"fa-regular":`regular`,fasl:`light`,"fa-light":`light`,fast:`thin`,"fa-thin":`thin`},"sharp-duotone":{fa:`solid`,fasds:`solid`,"fa-solid":`solid`,fasdr:`regular`,"fa-regular":`regular`,fasdl:`light`,"fa-light":`light`,fasdt:`thin`,"fa-thin":`thin`},slab:{"fa-regular":`regular`,faslr:`regular`},"slab-press":{"fa-regular":`regular`,faslpr:`regular`},thumbprint:{"fa-light":`light`,fatl:`light`},whiteboard:{"fa-semibold":`semibold`,fawsb:`semibold`},notdog:{"fa-solid":`solid`,fans:`solid`},"notdog-duo":{"fa-solid":`solid`,fands:`solid`},etch:{"fa-solid":`solid`,faes:`solid`},jelly:{"fa-regular":`regular`,fajr:`regular`},"jelly-fill":{"fa-regular":`regular`,fajfr:`regular`},"jelly-duo":{"fa-regular":`regular`,fajdr:`regular`},chisel:{"fa-regular":`regular`,facr:`regular`},utility:{"fa-semibold":`semibold`,fausb:`semibold`},"utility-duo":{"fa-semibold":`semibold`,faudsb:`semibold`},"utility-fill":{"fa-semibold":`semibold`,faufsb:`semibold`}},ye={GROUP:`duotone-group`,SWAP_OPACITY:`swap-opacity`,PRIMARY:`primary`,SECONDARY:`secondary`},be=[`fa-classic`,`fa-duotone`,`fa-sharp`,`fa-sharp-duotone`,`fa-thumbprint`,`fa-whiteboard`,`fa-notdog`,`fa-notdog-duo`,`fa-chisel`,`fa-etch`,`fa-jelly`,`fa-jelly-fill`,`fa-jelly-duo`,`fa-slab`,`fa-slab-press`,`fa-utility`,`fa-utility-duo`,`fa-utility-fill`],j=`classic`,xe=`duotone`,Se=`sharp`,Ce=`sharp-duotone`,we=`chisel`,Te=`etch`,Ee=`jelly`,De=`jelly-duo`,Oe=`jelly-fill`,ke=`notdog`,Ae=`notdog-duo`,je=`slab`,Me=`slab-press`,Ne=`thumbprint`,Pe=`utility`,Fe=`utility-duo`,Ie=`utility-fill`,Le=`whiteboard`,Re=`Classic`,ze=`Duotone`,Be=`Sharp`,Ve=`Sharp Duotone`,He=`Chisel`,Ue=`Etch`,We=`Jelly`,Ge=`Jelly Duo`,Ke=`Jelly Fill`,qe=`Notdog`,Je=`Notdog Duo`,Ye=`Slab`,Xe=`Slab Press`,Ze=`Thumbprint`,Qe=`Utility`,$e=`Utility Duo`,et=`Utility Fill`,tt=`Whiteboard`,nt=[j,xe,Se,Ce,we,Te,Ee,De,Oe,ke,Ae,je,Me,Ne,Pe,Fe,Ie,Le];he={},b(b(b(b(b(b(b(b(b(b(he,j,Re),xe,ze),Se,Be),Ce,Ve),we,He),Te,Ue),Ee,We),De,Ge),Oe,Ke),ke,qe),b(b(b(b(b(b(b(b(he,Ae,Je),je,Ye),Me,Xe),Ne,Ze),Pe,Qe),Fe,$e),Ie,et),Le,tt);var rt={classic:{900:`fas`,400:`far`,normal:`far`,300:`fal`,100:`fat`},duotone:{900:`fad`,400:`fadr`,300:`fadl`,100:`fadt`},sharp:{900:`fass`,400:`fasr`,300:`fasl`,100:`fast`},"sharp-duotone":{900:`fasds`,400:`fasdr`,300:`fasdl`,100:`fasdt`},slab:{400:`faslr`},"slab-press":{400:`faslpr`},whiteboard:{600:`fawsb`},thumbprint:{300:`fatl`},notdog:{900:`fans`},"notdog-duo":{900:`fands`},etch:{900:`faes`},chisel:{400:`facr`},jelly:{400:`fajr`},"jelly-fill":{400:`fajfr`},"jelly-duo":{400:`fajdr`},utility:{600:`fausb`},"utility-duo":{600:`faudsb`},"utility-fill":{600:`faufsb`}},it={"Font Awesome 7 Free":{900:`fas`,400:`far`},"Font Awesome 7 Pro":{900:`fas`,400:`far`,normal:`far`,300:`fal`,100:`fat`},"Font Awesome 7 Brands":{400:`fab`,normal:`fab`},"Font Awesome 7 Duotone":{900:`fad`,400:`fadr`,normal:`fadr`,300:`fadl`,100:`fadt`},"Font Awesome 7 Sharp":{900:`fass`,400:`fasr`,normal:`fasr`,300:`fasl`,100:`fast`},"Font Awesome 7 Sharp Duotone":{900:`fasds`,400:`fasdr`,normal:`fasdr`,300:`fasdl`,100:`fasdt`},"Font Awesome 7 Jelly":{400:`fajr`,normal:`fajr`},"Font Awesome 7 Jelly Fill":{400:`fajfr`,normal:`fajfr`},"Font Awesome 7 Jelly Duo":{400:`fajdr`,normal:`fajdr`},"Font Awesome 7 Slab":{400:`faslr`,normal:`faslr`},"Font Awesome 7 Slab Press":{400:`faslpr`,normal:`faslpr`},"Font Awesome 7 Thumbprint":{300:`fatl`,normal:`fatl`},"Font Awesome 7 Notdog":{900:`fans`,normal:`fans`},"Font Awesome 7 Notdog Duo":{900:`fands`,normal:`fands`},"Font Awesome 7 Etch":{900:`faes`,normal:`faes`},"Font Awesome 7 Chisel":{400:`facr`,normal:`facr`},"Font Awesome 7 Whiteboard":{600:`fawsb`,normal:`fawsb`},"Font Awesome 7 Utility":{600:`fausb`,normal:`fausb`},"Font Awesome 7 Utility Duo":{600:`faudsb`,normal:`faudsb`},"Font Awesome 7 Utility Fill":{600:`faufsb`,normal:`faufsb`}},at=new Map([[`classic`,{defaultShortPrefixId:`fas`,defaultStyleId:`solid`,styleIds:[`solid`,`regular`,`light`,`thin`,`brands`],futureStyleIds:[],defaultFontWeight:900}],[`duotone`,{defaultShortPrefixId:`fad`,defaultStyleId:`solid`,styleIds:[`solid`,`regular`,`light`,`thin`],futureStyleIds:[],defaultFontWeight:900}],[`sharp`,{defaultShortPrefixId:`fass`,defaultStyleId:`solid`,styleIds:[`solid`,`regular`,`light`,`thin`],futureStyleIds:[],defaultFontWeight:900}],[`sharp-duotone`,{defaultShortPrefixId:`fasds`,defaultStyleId:`solid`,styleIds:[`solid`,`regular`,`light`,`thin`],futureStyleIds:[],defaultFontWeight:900}],[`chisel`,{defaultShortPrefixId:`facr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`etch`,{defaultShortPrefixId:`faes`,defaultStyleId:`solid`,styleIds:[`solid`],futureStyleIds:[],defaultFontWeight:900}],[`jelly`,{defaultShortPrefixId:`fajr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`jelly-duo`,{defaultShortPrefixId:`fajdr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`jelly-fill`,{defaultShortPrefixId:`fajfr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`notdog`,{defaultShortPrefixId:`fans`,defaultStyleId:`solid`,styleIds:[`solid`],futureStyleIds:[],defaultFontWeight:900}],[`notdog-duo`,{defaultShortPrefixId:`fands`,defaultStyleId:`solid`,styleIds:[`solid`],futureStyleIds:[],defaultFontWeight:900}],[`slab`,{defaultShortPrefixId:`faslr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`slab-press`,{defaultShortPrefixId:`faslpr`,defaultStyleId:`regular`,styleIds:[`regular`],futureStyleIds:[],defaultFontWeight:400}],[`thumbprint`,{defaultShortPrefixId:`fatl`,defaultStyleId:`light`,styleIds:[`light`],futureStyleIds:[],defaultFontWeight:300}],[`utility`,{defaultShortPrefixId:`fausb`,defaultStyleId:`semibold`,styleIds:[`semibold`],futureStyleIds:[],defaultFontWeight:600}],[`utility-duo`,{defaultShortPrefixId:`faudsb`,defaultStyleId:`semibold`,styleIds:[`semibold`],futureStyleIds:[],defaultFontWeight:600}],[`utility-fill`,{defaultShortPrefixId:`faufsb`,defaultStyleId:`semibold`,styleIds:[`semibold`],futureStyleIds:[],defaultFontWeight:600}],[`whiteboard`,{defaultShortPrefixId:`fawsb`,defaultStyleId:`semibold`,styleIds:[`semibold`],futureStyleIds:[],defaultFontWeight:600}]]),ot={chisel:{regular:`facr`},classic:{brands:`fab`,light:`fal`,regular:`far`,solid:`fas`,thin:`fat`},duotone:{light:`fadl`,regular:`fadr`,solid:`fad`,thin:`fadt`},etch:{solid:`faes`},jelly:{regular:`fajr`},"jelly-duo":{regular:`fajdr`},"jelly-fill":{regular:`fajfr`},notdog:{solid:`fans`},"notdog-duo":{solid:`fands`},sharp:{light:`fasl`,regular:`fasr`,solid:`fass`,thin:`fast`},"sharp-duotone":{light:`fasdl`,regular:`fasdr`,solid:`fasds`,thin:`fasdt`},slab:{regular:`faslr`},"slab-press":{regular:`faslpr`},thumbprint:{light:`fatl`},utility:{semibold:`fausb`},"utility-duo":{semibold:`faudsb`},"utility-fill":{semibold:`faufsb`},whiteboard:{semibold:`fawsb`}},st=[`fak`,`fa-kit`,`fakd`,`fa-kit-duotone`],ct={kit:{fak:`kit`,"fa-kit":`kit`},"kit-duotone":{fakd:`kit-duotone`,"fa-kit-duotone":`kit-duotone`}},lt=[`kit`];b(b({},`kit`,`Kit`),`kit-duotone`,`Kit Duotone`);var ut={kit:{"fa-kit":`fak`},"kit-duotone":{"fa-kit-duotone":`fakd`}},dt={"Font Awesome Kit":{400:`fak`,normal:`fak`},"Font Awesome Kit Duotone":{400:`fakd`,normal:`fakd`}},ft={kit:{fak:`fa-kit`},"kit-duotone":{fakd:`fa-kit-duotone`}},pt={kit:{kit:`fak`},"kit-duotone":{"kit-duotone":`fakd`}},mt,ht={GROUP:`duotone-group`,SWAP_OPACITY:`swap-opacity`,PRIMARY:`primary`,SECONDARY:`secondary`},gt=[`fa-classic`,`fa-duotone`,`fa-sharp`,`fa-sharp-duotone`,`fa-thumbprint`,`fa-whiteboard`,`fa-notdog`,`fa-notdog-duo`,`fa-chisel`,`fa-etch`,`fa-jelly`,`fa-jelly-fill`,`fa-jelly-duo`,`fa-slab`,`fa-slab-press`,`fa-utility`,`fa-utility-duo`,`fa-utility-fill`];mt={},b(b(b(b(b(b(b(b(b(b(mt,`classic`,`Classic`),`duotone`,`Duotone`),`sharp`,`Sharp`),`sharp-duotone`,`Sharp Duotone`),`chisel`,`Chisel`),`etch`,`Etch`),`jelly`,`Jelly`),`jelly-duo`,`Jelly Duo`),`jelly-fill`,`Jelly Fill`),`notdog`,`Notdog`),b(b(b(b(b(b(b(b(mt,`notdog-duo`,`Notdog Duo`),`slab`,`Slab`),`slab-press`,`Slab Press`),`thumbprint`,`Thumbprint`),`utility`,`Utility`),`utility-duo`,`Utility Duo`),`utility-fill`,`Utility Fill`),`whiteboard`,`Whiteboard`),b(b({},`kit`,`Kit`),`kit-duotone`,`Kit Duotone`);var _t={classic:{"fa-brands":`fab`,"fa-duotone":`fad`,"fa-light":`fal`,"fa-regular":`far`,"fa-solid":`fas`,"fa-thin":`fat`},duotone:{"fa-regular":`fadr`,"fa-light":`fadl`,"fa-thin":`fadt`},sharp:{"fa-solid":`fass`,"fa-regular":`fasr`,"fa-light":`fasl`,"fa-thin":`fast`},"sharp-duotone":{"fa-solid":`fasds`,"fa-regular":`fasdr`,"fa-light":`fasdl`,"fa-thin":`fasdt`},slab:{"fa-regular":`faslr`},"slab-press":{"fa-regular":`faslpr`},whiteboard:{"fa-semibold":`fawsb`},thumbprint:{"fa-light":`fatl`},notdog:{"fa-solid":`fans`},"notdog-duo":{"fa-solid":`fands`},etch:{"fa-solid":`faes`},jelly:{"fa-regular":`fajr`},"jelly-fill":{"fa-regular":`fajfr`},"jelly-duo":{"fa-regular":`fajdr`},chisel:{"fa-regular":`facr`},utility:{"fa-semibold":`fausb`},"utility-duo":{"fa-semibold":`faudsb`},"utility-fill":{"fa-semibold":`faufsb`}},vt={classic:[`fas`,`far`,`fal`,`fat`,`fad`],duotone:[`fadr`,`fadl`,`fadt`],sharp:[`fass`,`fasr`,`fasl`,`fast`],"sharp-duotone":[`fasds`,`fasdr`,`fasdl`,`fasdt`],slab:[`faslr`],"slab-press":[`faslpr`],whiteboard:[`fawsb`],thumbprint:[`fatl`],notdog:[`fans`],"notdog-duo":[`fands`],etch:[`faes`],jelly:[`fajr`],"jelly-fill":[`fajfr`],"jelly-duo":[`fajdr`],chisel:[`facr`],utility:[`fausb`],"utility-duo":[`faudsb`],"utility-fill":[`faufsb`]},yt={classic:{fab:`fa-brands`,fad:`fa-duotone`,fal:`fa-light`,far:`fa-regular`,fas:`fa-solid`,fat:`fa-thin`},duotone:{fadr:`fa-regular`,fadl:`fa-light`,fadt:`fa-thin`},sharp:{fass:`fa-solid`,fasr:`fa-regular`,fasl:`fa-light`,fast:`fa-thin`},"sharp-duotone":{fasds:`fa-solid`,fasdr:`fa-regular`,fasdl:`fa-light`,fasdt:`fa-thin`},slab:{faslr:`fa-regular`},"slab-press":{faslpr:`fa-regular`},whiteboard:{fawsb:`fa-semibold`},thumbprint:{fatl:`fa-light`},notdog:{fans:`fa-solid`},"notdog-duo":{fands:`fa-solid`},etch:{faes:`fa-solid`},jelly:{fajr:`fa-regular`},"jelly-fill":{fajfr:`fa-regular`},"jelly-duo":{fajdr:`fa-regular`},chisel:{facr:`fa-regular`},utility:{fausb:`fa-semibold`},"utility-duo":{faudsb:`fa-semibold`},"utility-fill":{faufsb:`fa-semibold`}},bt=`fa.fas.far.fal.fat.fad.fadr.fadl.fadt.fab.fass.fasr.fasl.fast.fasds.fasdr.fasdl.fasdt.faslr.faslpr.fawsb.fatl.fans.fands.faes.fajr.fajfr.fajdr.facr.fausb.faudsb.faufsb`.split(`.`).concat(gt,[`fa-solid`,`fa-regular`,`fa-light`,`fa-thin`,`fa-duotone`,`fa-brands`,`fa-semibold`]),xt=[`solid`,`regular`,`light`,`thin`,`duotone`,`brands`,`semibold`],St=[1,2,3,4,5,6,7,8,9,10],Ct=St.concat([11,12,13,14,15,16,17,18,19,20]),wt=[].concat(w(Object.keys(vt)),xt,[`aw`,`fw`,`pull-left`,`pull-right`],[`2xs`,`xs`,`sm`,`lg`,`xl`,`2xl`,`beat`,`border`,`fade`,`beat-fade`,`bounce`,`flip-both`,`flip-horizontal`,`flip-vertical`,`flip`,`inverse`,`layers`,`layers-bottom-left`,`layers-bottom-right`,`layers-counter`,`layers-text`,`layers-top-left`,`layers-top-right`,`li`,`pull-end`,`pull-start`,`pulse`,`rotate-180`,`rotate-270`,`rotate-90`,`rotate-by`,`shake`,`spin-pulse`,`spin-reverse`,`spin`,`stack-1x`,`stack-2x`,`stack`,`ul`,`width-auto`,`width-fixed`,ht.GROUP,ht.SWAP_OPACITY,ht.PRIMARY,ht.SECONDARY],St.map(function(e){return`${e}x`}),Ct.map(function(e){return`w-${e}`})),Tt={"Font Awesome 5 Free":{900:`fas`,400:`far`},"Font Awesome 5 Pro":{900:`fas`,400:`far`,normal:`far`,300:`fal`},"Font Awesome 5 Brands":{400:`fab`,normal:`fab`},"Font Awesome 5 Duotone":{900:`fad`}},M=`___FONT_AWESOME___`,Et=16,Dt=`fa`,Ot=`svg-inline--fa`,N=`data-fa-i2svg`,kt=`data-fa-pseudo-element`,At=`data-fa-pseudo-element-pending`,jt=`data-prefix`,Mt=`data-icon`,Nt=`fontawesome-i2svg`,Pt=`async`,Ft=[`HTML`,`HEAD`,`STYLE`,`SCRIPT`],It=[`::before`,`::after`,`:before`,`:after`],Lt=function(){try{return!0}catch{return!1}}();function Rt(e){return new Proxy(e,{get:function(e,t){return t in e?e[t]:e[j]}})}var zt=C({},ve);zt[j]=C(C(C(C({},{"fa-duotone":`duotone`}),ve[j]),ct.kit),ct[`kit-duotone`]);var Bt=Rt(zt),Vt=C({},ot);Vt[j]=C(C(C(C({},{duotone:`fad`}),Vt[j]),pt.kit),pt[`kit-duotone`]);var Ht=Rt(Vt),Ut=C({},yt);Ut[j]=C(C({},Ut[j]),ft.kit);var Wt=Rt(Ut),Gt=C({},_t);Gt[j]=C(C({},Gt[j]),ut.kit),Rt(Gt);var Kt=ge,qt=`fa-layers-text`,Jt=_e;Rt(C({},rt));var Yt=[`class`,`data-prefix`,`data-icon`,`data-fa-transform`,`data-fa-mask`],Xt=ye,Zt=[].concat(w(lt),w(wt)),P=O.FontAwesomeConfig||{};function Qt(e){var t=k.querySelector(`script[`+e+`]`);if(t)return t.getAttribute(e)}function $t(e){return e===``?!0:e===`false`?!1:e===`true`?!0:e}k&&typeof k.querySelector==`function`&&[[`data-family-prefix`,`familyPrefix`],[`data-css-prefix`,`cssPrefix`],[`data-family-default`,`familyDefault`],[`data-style-default`,`styleDefault`],[`data-replacement-class`,`replacementClass`],[`data-auto-replace-svg`,`autoReplaceSvg`],[`data-auto-add-css`,`autoAddCss`],[`data-search-pseudo-elements`,`searchPseudoElements`],[`data-search-pseudo-elements-warnings`,`searchPseudoElementsWarnings`],[`data-search-pseudo-elements-full-scan`,`searchPseudoElementsFullScan`],[`data-observe-mutations`,`observeMutations`],[`data-mutate-approach`,`mutateApproach`],[`data-keep-original-source`,`keepOriginalSource`],[`data-measure-performance`,`measurePerformance`],[`data-show-missing-icons`,`showMissingIcons`]].forEach(function(e){var t=re(e,2),n=t[0],r=t[1],i=$t(Qt(n));i!=null&&(P[r]=i)});var en={styleDefault:`solid`,familyDefault:j,cssPrefix:Dt,replacementClass:Ot,autoReplaceSvg:!0,autoAddCss:!0,searchPseudoElements:!1,searchPseudoElementsWarnings:!0,searchPseudoElementsFullScan:!1,observeMutations:!0,mutateApproach:`async`,keepOriginalSource:!0,measurePerformance:!1,showMissingIcons:!0};P.familyPrefix&&(P.cssPrefix=P.familyPrefix);var F=C(C({},en),P);F.autoReplaceSvg||(F.observeMutations=!1);var I={};Object.keys(en).forEach(function(e){Object.defineProperty(I,e,{enumerable:!0,set:function(t){F[e]=t,tn.forEach(function(e){return e(I)})},get:function(){return F[e]}})}),Object.defineProperty(I,`familyPrefix`,{enumerable:!0,set:function(e){F.cssPrefix=e,tn.forEach(function(e){return e(I)})},get:function(){return F.cssPrefix}}),O.FontAwesomeConfig=I;var tn=[];function nn(e){return tn.push(e),function(){tn.splice(tn.indexOf(e),1)}}var L=Et,R={size:16,x:0,y:0,rotate:0,flipX:!1,flipY:!1};function rn(e){if(!(!e||!A)){var t=k.createElement(`style`);t.setAttribute(`type`,`text/css`),t.innerHTML=e;for(var n=k.head.childNodes,r=null,i=n.length-1;i>-1;i--){var a=n[i],o=(a.tagName||``).toUpperCase();[`STYLE`,`LINK`].indexOf(o)>-1&&(r=a)}return k.head.insertBefore(t,r),e}}var an=`0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ`;function on(){for(var e=12,t=``;e-- >0;)t+=an[Math.random()*62|0];return t}function z(e){for(var t=[],n=(e||[]).length>>>0;n--;)t[n]=e[n];return t}function sn(e){return e.classList?z(e.classList):(e.getAttribute(`class`)||``).split(` `).filter(function(e){return e})}function cn(e){return`${e}`.replace(/&/g,`&amp;`).replace(/"/g,`&quot;`).replace(/'/g,`&#39;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`)}function ln(e){return Object.keys(e||{}).reduce(function(t,n){return t+`${n}="${cn(e[n])}" `},``).trim()}function un(e){return Object.keys(e||{}).reduce(function(t,n){return t+`${n}: ${e[n].trim()};`},``)}function dn(e){return e.size!==R.size||e.x!==R.x||e.y!==R.y||e.rotate!==R.rotate||e.flipX||e.flipY}function fn(e){var t=e.transform,n=e.containerWidth,r=e.iconWidth;return{outer:{transform:`translate(${n/2} 256)`},inner:{transform:`${`translate(${t.x*32}, ${t.y*32}) `} ${`scale(${t.size/16*(t.flipX?-1:1)}, ${t.size/16*(t.flipY?-1:1)}) `} ${`rotate(${t.rotate} 0 0)`}`},path:{transform:`translate(${r/2*-1} -256)`}}}function pn(e){var t=e.transform,n=e.width,r=n===void 0?Et:n,i=e.height,a=i===void 0?Et:i,o=e.startCentered,s=o===void 0?!1:o,c=``;return s&&me?c+=`translate(${t.x/L-r/2}em, ${t.y/L-a/2}em) `:s?c+=`translate(calc(-50% + ${t.x/L}em), calc(-50% + ${t.y/L}em)) `:c+=`translate(${t.x/L}em, ${t.y/L}em) `,c+=`scale(${t.size/L*(t.flipX?-1:1)}, ${t.size/L*(t.flipY?-1:1)}) `,c+=`rotate(${t.rotate}deg) `,c}var mn=`:root, :host {
  --fa-font-solid: normal 900 1em/1 "Font Awesome 7 Free";
  --fa-font-regular: normal 400 1em/1 "Font Awesome 7 Free";
  --fa-font-light: normal 300 1em/1 "Font Awesome 7 Pro";
  --fa-font-thin: normal 100 1em/1 "Font Awesome 7 Pro";
  --fa-font-duotone: normal 900 1em/1 "Font Awesome 7 Duotone";
  --fa-font-duotone-regular: normal 400 1em/1 "Font Awesome 7 Duotone";
  --fa-font-duotone-light: normal 300 1em/1 "Font Awesome 7 Duotone";
  --fa-font-duotone-thin: normal 100 1em/1 "Font Awesome 7 Duotone";
  --fa-font-brands: normal 400 1em/1 "Font Awesome 7 Brands";
  --fa-font-sharp-solid: normal 900 1em/1 "Font Awesome 7 Sharp";
  --fa-font-sharp-regular: normal 400 1em/1 "Font Awesome 7 Sharp";
  --fa-font-sharp-light: normal 300 1em/1 "Font Awesome 7 Sharp";
  --fa-font-sharp-thin: normal 100 1em/1 "Font Awesome 7 Sharp";
  --fa-font-sharp-duotone-solid: normal 900 1em/1 "Font Awesome 7 Sharp Duotone";
  --fa-font-sharp-duotone-regular: normal 400 1em/1 "Font Awesome 7 Sharp Duotone";
  --fa-font-sharp-duotone-light: normal 300 1em/1 "Font Awesome 7 Sharp Duotone";
  --fa-font-sharp-duotone-thin: normal 100 1em/1 "Font Awesome 7 Sharp Duotone";
  --fa-font-slab-regular: normal 400 1em/1 "Font Awesome 7 Slab";
  --fa-font-slab-press-regular: normal 400 1em/1 "Font Awesome 7 Slab Press";
  --fa-font-whiteboard-semibold: normal 600 1em/1 "Font Awesome 7 Whiteboard";
  --fa-font-thumbprint-light: normal 300 1em/1 "Font Awesome 7 Thumbprint";
  --fa-font-notdog-solid: normal 900 1em/1 "Font Awesome 7 Notdog";
  --fa-font-notdog-duo-solid: normal 900 1em/1 "Font Awesome 7 Notdog Duo";
  --fa-font-etch-solid: normal 900 1em/1 "Font Awesome 7 Etch";
  --fa-font-jelly-regular: normal 400 1em/1 "Font Awesome 7 Jelly";
  --fa-font-jelly-fill-regular: normal 400 1em/1 "Font Awesome 7 Jelly Fill";
  --fa-font-jelly-duo-regular: normal 400 1em/1 "Font Awesome 7 Jelly Duo";
  --fa-font-chisel-regular: normal 400 1em/1 "Font Awesome 7 Chisel";
  --fa-font-utility-semibold: normal 600 1em/1 "Font Awesome 7 Utility";
  --fa-font-utility-duo-semibold: normal 600 1em/1 "Font Awesome 7 Utility Duo";
  --fa-font-utility-fill-semibold: normal 600 1em/1 "Font Awesome 7 Utility Fill";
}

.svg-inline--fa {
  box-sizing: content-box;
  display: var(--fa-display, inline-block);
  height: 1em;
  overflow: visible;
  vertical-align: -0.125em;
  width: var(--fa-width, 1.25em);
}
.svg-inline--fa.fa-2xs {
  vertical-align: 0.1em;
}
.svg-inline--fa.fa-xs {
  vertical-align: 0em;
}
.svg-inline--fa.fa-sm {
  vertical-align: -0.0714285714em;
}
.svg-inline--fa.fa-lg {
  vertical-align: -0.2em;
}
.svg-inline--fa.fa-xl {
  vertical-align: -0.25em;
}
.svg-inline--fa.fa-2xl {
  vertical-align: -0.3125em;
}
.svg-inline--fa.fa-pull-left,
.svg-inline--fa .fa-pull-start {
  float: inline-start;
  margin-inline-end: var(--fa-pull-margin, 0.3em);
}
.svg-inline--fa.fa-pull-right,
.svg-inline--fa .fa-pull-end {
  float: inline-end;
  margin-inline-start: var(--fa-pull-margin, 0.3em);
}
.svg-inline--fa.fa-li {
  width: var(--fa-li-width, 2em);
  inset-inline-start: calc(-1 * var(--fa-li-width, 2em));
  inset-block-start: 0.25em; /* syncing vertical alignment with Web Font rendering */
}

.fa-layers-counter, .fa-layers-text {
  display: inline-block;
  position: absolute;
  text-align: center;
}

.fa-layers {
  display: inline-block;
  height: 1em;
  position: relative;
  text-align: center;
  vertical-align: -0.125em;
  width: var(--fa-width, 1.25em);
}
.fa-layers .svg-inline--fa {
  inset: 0;
  margin: auto;
  position: absolute;
  transform-origin: center center;
}

.fa-layers-text {
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  transform-origin: center center;
}

.fa-layers-counter {
  background-color: var(--fa-counter-background-color, #ff253a);
  border-radius: var(--fa-counter-border-radius, 1em);
  box-sizing: border-box;
  color: var(--fa-inverse, #fff);
  line-height: var(--fa-counter-line-height, 1);
  max-width: var(--fa-counter-max-width, 5em);
  min-width: var(--fa-counter-min-width, 1.5em);
  overflow: hidden;
  padding: var(--fa-counter-padding, 0.25em 0.5em);
  right: var(--fa-right, 0);
  text-overflow: ellipsis;
  top: var(--fa-top, 0);
  transform: scale(var(--fa-counter-scale, 0.25));
  transform-origin: top right;
}

.fa-layers-bottom-right {
  bottom: var(--fa-bottom, 0);
  right: var(--fa-right, 0);
  top: auto;
  transform: scale(var(--fa-layers-scale, 0.25));
  transform-origin: bottom right;
}

.fa-layers-bottom-left {
  bottom: var(--fa-bottom, 0);
  left: var(--fa-left, 0);
  right: auto;
  top: auto;
  transform: scale(var(--fa-layers-scale, 0.25));
  transform-origin: bottom left;
}

.fa-layers-top-right {
  top: var(--fa-top, 0);
  right: var(--fa-right, 0);
  transform: scale(var(--fa-layers-scale, 0.25));
  transform-origin: top right;
}

.fa-layers-top-left {
  left: var(--fa-left, 0);
  right: auto;
  top: var(--fa-top, 0);
  transform: scale(var(--fa-layers-scale, 0.25));
  transform-origin: top left;
}

.fa-1x {
  font-size: 1em;
}

.fa-2x {
  font-size: 2em;
}

.fa-3x {
  font-size: 3em;
}

.fa-4x {
  font-size: 4em;
}

.fa-5x {
  font-size: 5em;
}

.fa-6x {
  font-size: 6em;
}

.fa-7x {
  font-size: 7em;
}

.fa-8x {
  font-size: 8em;
}

.fa-9x {
  font-size: 9em;
}

.fa-10x {
  font-size: 10em;
}

.fa-2xs {
  font-size: calc(10 / 16 * 1em); /* converts a 10px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 10 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 10 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-xs {
  font-size: calc(12 / 16 * 1em); /* converts a 12px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 12 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 12 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-sm {
  font-size: calc(14 / 16 * 1em); /* converts a 14px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 14 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 14 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-lg {
  font-size: calc(20 / 16 * 1em); /* converts a 20px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 20 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 20 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-xl {
  font-size: calc(24 / 16 * 1em); /* converts a 24px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 24 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 24 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-2xl {
  font-size: calc(32 / 16 * 1em); /* converts a 32px size into an em-based value that's relative to the scale's 16px base */
  line-height: calc(1 / 32 * 1em); /* sets the line-height of the icon back to that of it's parent */
  vertical-align: calc((6 / 32 - 0.375) * 1em); /* vertically centers the icon taking into account the surrounding text's descender */
}

.fa-width-auto {
  --fa-width: auto;
}

.fa-fw,
.fa-width-fixed {
  --fa-width: 1.25em;
}

.fa-ul {
  list-style-type: none;
  margin-inline-start: var(--fa-li-margin, 2.5em);
  padding-inline-start: 0;
}
.fa-ul > li {
  position: relative;
}

.fa-li {
  inset-inline-start: calc(-1 * var(--fa-li-width, 2em));
  position: absolute;
  text-align: center;
  width: var(--fa-li-width, 2em);
  line-height: inherit;
}

/* Heads Up: Bordered Icons will not be supported in the future!
  - This feature will be deprecated in the next major release of Font Awesome (v8)!
  - You may continue to use it in this version *v7), but it will not be supported in Font Awesome v8.
*/
/* Notes:
* --@{v.$css-prefix}-border-width = 1/16 by default (to render as ~1px based on a 16px default font-size)
* --@{v.$css-prefix}-border-padding =
  ** 3/16 for vertical padding (to give ~2px of vertical whitespace around an icon considering it's vertical alignment)
  ** 4/16 for horizontal padding (to give ~4px of horizontal whitespace around an icon)
*/
.fa-border {
  border-color: var(--fa-border-color, #eee);
  border-radius: var(--fa-border-radius, 0.1em);
  border-style: var(--fa-border-style, solid);
  border-width: var(--fa-border-width, 0.0625em);
  box-sizing: var(--fa-border-box-sizing, content-box);
  padding: var(--fa-border-padding, 0.1875em 0.25em);
}

.fa-pull-left,
.fa-pull-start {
  float: inline-start;
  margin-inline-end: var(--fa-pull-margin, 0.3em);
}

.fa-pull-right,
.fa-pull-end {
  float: inline-end;
  margin-inline-start: var(--fa-pull-margin, 0.3em);
}

.fa-beat {
  animation-name: fa-beat;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-in-out);
}

.fa-bounce {
  animation-name: fa-bounce;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, cubic-bezier(0.28, 0.84, 0.42, 1));
}

.fa-fade {
  animation-name: fa-fade;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, cubic-bezier(0.4, 0, 0.6, 1));
}

.fa-beat-fade {
  animation-name: fa-beat-fade;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, cubic-bezier(0.4, 0, 0.6, 1));
}

.fa-flip {
  animation-name: fa-flip;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, ease-in-out);
}

.fa-shake {
  animation-name: fa-shake;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, linear);
}

.fa-spin {
  animation-name: fa-spin;
  animation-delay: var(--fa-animation-delay, 0s);
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 2s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, linear);
}

.fa-spin-reverse {
  --fa-animation-direction: reverse;
}

.fa-pulse,
.fa-spin-pulse {
  animation-name: fa-spin;
  animation-direction: var(--fa-animation-direction, normal);
  animation-duration: var(--fa-animation-duration, 1s);
  animation-iteration-count: var(--fa-animation-iteration-count, infinite);
  animation-timing-function: var(--fa-animation-timing, steps(8));
}

@media (prefers-reduced-motion: reduce) {
  .fa-beat,
  .fa-bounce,
  .fa-fade,
  .fa-beat-fade,
  .fa-flip,
  .fa-pulse,
  .fa-shake,
  .fa-spin,
  .fa-spin-pulse {
    animation: none !important;
    transition: none !important;
  }
}
@keyframes fa-beat {
  0%, 90% {
    transform: scale(1);
  }
  45% {
    transform: scale(var(--fa-beat-scale, 1.25));
  }
}
@keyframes fa-bounce {
  0% {
    transform: scale(1, 1) translateY(0);
  }
  10% {
    transform: scale(var(--fa-bounce-start-scale-x, 1.1), var(--fa-bounce-start-scale-y, 0.9)) translateY(0);
  }
  30% {
    transform: scale(var(--fa-bounce-jump-scale-x, 0.9), var(--fa-bounce-jump-scale-y, 1.1)) translateY(var(--fa-bounce-height, -0.5em));
  }
  50% {
    transform: scale(var(--fa-bounce-land-scale-x, 1.05), var(--fa-bounce-land-scale-y, 0.95)) translateY(0);
  }
  57% {
    transform: scale(1, 1) translateY(var(--fa-bounce-rebound, -0.125em));
  }
  64% {
    transform: scale(1, 1) translateY(0);
  }
  100% {
    transform: scale(1, 1) translateY(0);
  }
}
@keyframes fa-fade {
  50% {
    opacity: var(--fa-fade-opacity, 0.4);
  }
}
@keyframes fa-beat-fade {
  0%, 100% {
    opacity: var(--fa-beat-fade-opacity, 0.4);
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(var(--fa-beat-fade-scale, 1.125));
  }
}
@keyframes fa-flip {
  50% {
    transform: rotate3d(var(--fa-flip-x, 0), var(--fa-flip-y, 1), var(--fa-flip-z, 0), var(--fa-flip-angle, -180deg));
  }
}
@keyframes fa-shake {
  0% {
    transform: rotate(-15deg);
  }
  4% {
    transform: rotate(15deg);
  }
  8%, 24% {
    transform: rotate(-18deg);
  }
  12%, 28% {
    transform: rotate(18deg);
  }
  16% {
    transform: rotate(-22deg);
  }
  20% {
    transform: rotate(22deg);
  }
  32% {
    transform: rotate(-12deg);
  }
  36% {
    transform: rotate(12deg);
  }
  40%, 100% {
    transform: rotate(0deg);
  }
}
@keyframes fa-spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
.fa-rotate-90 {
  transform: rotate(90deg);
}

.fa-rotate-180 {
  transform: rotate(180deg);
}

.fa-rotate-270 {
  transform: rotate(270deg);
}

.fa-flip-horizontal {
  transform: scale(-1, 1);
}

.fa-flip-vertical {
  transform: scale(1, -1);
}

.fa-flip-both,
.fa-flip-horizontal.fa-flip-vertical {
  transform: scale(-1, -1);
}

.fa-rotate-by {
  transform: rotate(var(--fa-rotate-angle, 0));
}

.svg-inline--fa .fa-primary {
  fill: var(--fa-primary-color, currentColor);
  opacity: var(--fa-primary-opacity, 1);
}

.svg-inline--fa .fa-secondary {
  fill: var(--fa-secondary-color, currentColor);
  opacity: var(--fa-secondary-opacity, 0.4);
}

.svg-inline--fa.fa-swap-opacity .fa-primary {
  opacity: var(--fa-secondary-opacity, 0.4);
}

.svg-inline--fa.fa-swap-opacity .fa-secondary {
  opacity: var(--fa-primary-opacity, 1);
}

.svg-inline--fa mask .fa-primary,
.svg-inline--fa mask .fa-secondary {
  fill: black;
}

.svg-inline--fa.fa-inverse {
  fill: var(--fa-inverse, #fff);
}

.fa-stack {
  display: inline-block;
  height: 2em;
  line-height: 2em;
  position: relative;
  vertical-align: middle;
  width: 2.5em;
}

.fa-inverse {
  color: var(--fa-inverse, #fff);
}

.svg-inline--fa.fa-stack-1x {
  --fa-width: 1.25em;
  height: 1em;
  width: var(--fa-width);
}
.svg-inline--fa.fa-stack-2x {
  --fa-width: 2.5em;
  height: 2em;
  width: var(--fa-width);
}

.fa-stack-1x,
.fa-stack-2x {
  inset: 0;
  margin: auto;
  position: absolute;
  z-index: var(--fa-stack-z-index, auto);
}`;function hn(){var e=Dt,t=Ot,n=I.cssPrefix,r=I.replacementClass,i=mn;if(n!==e||r!==t){var a=RegExp(`\\.${e}\\-`,`g`),o=RegExp(`\\--${e}\\-`,`g`),s=RegExp(`\\.${t}`,`g`);i=i.replace(a,`.${n}-`).replace(o,`--${n}-`).replace(s,`.${r}`)}return i}var gn=!1;function _n(){I.autoAddCss&&!gn&&(rn(hn()),gn=!0)}var vn={mixout:function(){return{dom:{css:hn,insertCss:_n}}},hooks:function(){return{beforeDOMElementCreation:function(){_n()},beforeI2svg:function(){_n()}}}},B=O||{};B[M]||(B[M]={}),B[M].styles||(B[M].styles={}),B[M].hooks||(B[M].hooks={}),B[M].shims||(B[M].shims=[]);var V=B[M],yn=[],bn=function(){k.removeEventListener(`DOMContentLoaded`,bn),xn=1,yn.map(function(e){return e()})},xn=!1;A&&(xn=(k.documentElement.doScroll?/^loaded|^c/:/^loaded|^i|^c/).test(k.readyState),xn||k.addEventListener(`DOMContentLoaded`,bn));function Sn(e){A&&(xn?setTimeout(e,0):yn.push(e))}function Cn(e){var t=e.tag,n=e.attributes,r=n===void 0?{}:n,i=e.children,a=i===void 0?[]:i;return typeof e==`string`?cn(e):`<${t} ${ln(r)}>${a.map(Cn).join(``)}</${t}>`}function wn(e,t,n){if(e&&e[t]&&e[t][n])return{prefix:t,iconName:n,icon:e[t][n]}}var Tn=function(e,t){return function(n,r,i,a){return e.call(t,n,r,i,a)}},En=function(e,t,n,r){var i=Object.keys(e),a=i.length,o=r===void 0?t:Tn(t,r),s,c,l;for(n===void 0?(s=1,l=e[i[0]]):(s=0,l=n);s<a;s++)c=i[s],l=o(l,e[c],c,e);return l};function Dn(e){return w(e).length===1?e.codePointAt(0).toString(16):null}function On(e){return Object.keys(e).reduce(function(t,n){var r=e[n];return r.icon?t[r.iconName]=r.icon:t[n]=r,t},{})}function kn(e,t){var n=(arguments.length>2&&arguments[2]!==void 0?arguments[2]:{}).skipHooks,r=n===void 0?!1:n,i=On(t);typeof V.hooks.addPack==`function`&&!r?V.hooks.addPack(e,On(t)):V.styles[e]=C(C({},V.styles[e]||{}),i),e===`fas`&&kn(`fa`,t)}var H=V.styles,An=V.shims,jn=Object.keys(Wt),Mn=jn.reduce(function(e,t){return e[t]=Object.keys(Wt[t]),e},{}),Nn=null,Pn={},Fn={},In={},Ln={},Rn={};function zn(e){return~Zt.indexOf(e)}function Bn(e,t){var n=t.split(`-`),r=n[0],i=n.slice(1).join(`-`);return r===e&&i!==``&&!zn(i)?i:null}var Vn=function(){var e=function(e){return En(H,function(t,n,r){return t[r]=En(n,e,{}),t},{})};Pn=e(function(e,t,n){return t[3]&&(e[t[3]]=n),t[2]&&t[2].filter(function(e){return typeof e==`number`}).forEach(function(t){e[t.toString(16)]=n}),e}),Fn=e(function(e,t,n){return e[n]=n,t[2]&&t[2].filter(function(e){return typeof e==`string`}).forEach(function(t){e[t]=n}),e}),Rn=e(function(e,t,n){var r=t[2];return e[n]=n,r.forEach(function(t){e[t]=n}),e});var t=`far`in H||I.autoFetchSvg,n=En(An,function(e,n){var r=n[0],i=n[1],a=n[2];return i===`far`&&!t&&(i=`fas`),typeof r==`string`&&(e.names[r]={prefix:i,iconName:a}),typeof r==`number`&&(e.unicodes[r.toString(16)]={prefix:i,iconName:a}),e},{names:{},unicodes:{}});In=n.names,Ln=n.unicodes,Nn=Jn(I.styleDefault,{family:I.familyDefault})};nn(function(e){Nn=Jn(e.styleDefault,{family:I.familyDefault})}),Vn();function Hn(e,t){return(Pn[e]||{})[t]}function Un(e,t){return(Fn[e]||{})[t]}function U(e,t){return(Rn[e]||{})[t]}function Wn(e){return In[e]||{prefix:null,iconName:null}}function Gn(e){var t=Ln[e],n=Hn(`fas`,e);return t||(n?{prefix:`fas`,iconName:n}:null)||{prefix:null,iconName:null}}function W(){return Nn}var Kn=function(){return{prefix:null,iconName:null,rest:[]}};function qn(e){var t=j,n=jn.reduce(function(e,t){return e[t]=`${I.cssPrefix}-${t}`,e},{});return nt.forEach(function(r){(e.includes(n[r])||e.some(function(e){return Mn[r].includes(e)}))&&(t=r)}),t}function Jn(e){var t=(arguments.length>1&&arguments[1]!==void 0?arguments[1]:{}).family,n=t===void 0?j:t,r=Bt[n][e];if(n===xe&&!e)return`fad`;var i=Ht[n][e]||Ht[n][r],a=e in V.styles?e:null;return i||a||null}function Yn(e){var t=[],n=null;return e.forEach(function(e){var r=Bn(I.cssPrefix,e);r?n=r:e&&t.push(e)}),{iconName:n,rest:t}}function Xn(e){return e.sort().filter(function(e,t,n){return n.indexOf(e)===t})}var Zn=bt.concat(st);function Qn(e){var t=(arguments.length>1&&arguments[1]!==void 0?arguments[1]:{}).skipLookups,n=t===void 0?!1:t,r=null,i=Xn(e.filter(function(e){return Zn.includes(e)})),a=Xn(e.filter(function(e){return!Zn.includes(e)})),o=re(i.filter(function(e){return r=e,!be.includes(e)}),1)[0],s=o===void 0?null:o,c=qn(i),l=C(C({},Yn(a)),{},{prefix:Jn(s,{family:c})});return C(C(C({},l),nr({values:e,family:c,styles:H,config:I,canonical:l,givenPrefix:r})),$n(n,r,l))}function $n(e,t,n){var r=n.prefix,i=n.iconName;if(e||!r||!i)return{prefix:r,iconName:i};var a=t===`fa`?Wn(i):{},o=U(r,i);return i=a.iconName||o||i,r=a.prefix||r,r===`far`&&!H.far&&H.fas&&!I.autoFetchSvg&&(r=`fas`),{prefix:r,iconName:i}}var er=nt.filter(function(e){return e!==j||e!==xe}),tr=Object.keys(yt).filter(function(e){return e!==j}).map(function(e){return Object.keys(yt[e])}).flat();function nr(e){var t=e.values,n=e.family,r=e.canonical,i=e.givenPrefix,a=i===void 0?``:i,o=e.styles,s=o===void 0?{}:o,c=e.config,l=c===void 0?{}:c,u=n===xe,d=t.includes(`fa-duotone`)||t.includes(`fad`),f=l.familyDefault===`duotone`,p=r.prefix===`fad`||r.prefix===`fa-duotone`;return!u&&(d||f||p)&&(r.prefix=`fad`),(t.includes(`fa-brands`)||t.includes(`fab`))&&(r.prefix=`fab`),!r.prefix&&er.includes(n)&&(Object.keys(s).find(function(e){return tr.includes(e)})||l.autoFetchSvg)&&(r.prefix=at.get(n).defaultShortPrefixId,r.iconName=U(r.prefix,r.iconName)||r.iconName),(r.prefix===`fa`||a===`fa`)&&(r.prefix=W()||`fas`),r}var rr=function(){function e(){g(this,e),this.definitions={}}return v(e,[{key:`add`,value:function(){var e=this,t=[...arguments].reduce(this._pullDefinitions,{});Object.keys(t).forEach(function(n){e.definitions[n]=C(C({},e.definitions[n]||{}),t[n]),kn(n,t[n]);var r=Wt[j][n];r&&kn(r,t[n]),Vn()})}},{key:`reset`,value:function(){this.definitions={}}},{key:`_pullDefinitions`,value:function(e,t){var n=t.prefix&&t.iconName&&t.icon?{0:t}:t;return Object.keys(n).map(function(t){var r=n[t],i=r.prefix,a=r.iconName,o=r.icon,s=o[2];e[i]||(e[i]={}),s.length>0&&s.forEach(function(t){typeof t==`string`&&(e[i][t]=o)}),e[i][a]=o}),e}}])}(),ir=[],G={},K={},ar=Object.keys(K);function or(e,t){var n=t.mixoutsTo;return ir=e,G={},Object.keys(K).forEach(function(e){ar.indexOf(e)===-1&&delete K[e]}),ir.forEach(function(e){var t=e.mixout?e.mixout():{};if(Object.keys(t).forEach(function(e){typeof t[e]==`function`&&(n[e]=t[e]),T(t[e])===`object`&&Object.keys(t[e]).forEach(function(r){n[e]||(n[e]={}),n[e][r]=t[e][r]})}),e.hooks){var r=e.hooks();Object.keys(r).forEach(function(e){G[e]||(G[e]=[]),G[e].push(r[e])})}e.provides&&e.provides(K)}),n}function sr(e,t){var n=[...arguments].slice(2);return(G[e]||[]).forEach(function(e){t=e.apply(null,[t].concat(n))}),t}function q(e){var t=[...arguments].slice(1);(G[e]||[]).forEach(function(e){e.apply(null,t)})}function J(){var e=arguments[0],t=Array.prototype.slice.call(arguments,1);return K[e]?K[e].apply(null,t):void 0}function cr(e){e.prefix===`fa`&&(e.prefix=`fas`);var t=e.iconName,n=e.prefix||W();if(t)return t=U(n,t)||t,wn(lr.definitions,n,t)||wn(V.styles,n,t)}var lr=new rr,Y={noAuto:function(){I.autoReplaceSvg=!1,I.observeMutations=!1,q(`noAuto`)},config:I,dom:{i2svg:function(){var e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:{};return A?(q(`beforeI2svg`,e),J(`pseudoElements2svg`,e),J(`i2svg`,e)):Promise.reject(Error(`Operation requires a DOM of some kind.`))},watch:function(){var e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:{},t=e.autoReplaceSvgRoot;I.autoReplaceSvg===!1&&(I.autoReplaceSvg=!0),I.observeMutations=!0,Sn(function(){ur({autoReplaceSvgRoot:t}),q(`watch`,e)})}},parse:{icon:function(e){if(e===null)return null;if(T(e)===`object`&&e.prefix&&e.iconName)return{prefix:e.prefix,iconName:U(e.prefix,e.iconName)||e.iconName};if(Array.isArray(e)&&e.length===2){var t=e[1].indexOf(`fa-`)===0?e[1].slice(3):e[1],n=Jn(e[0]);return{prefix:n,iconName:U(n,t)||t}}if(typeof e==`string`&&(e.indexOf(`${I.cssPrefix}-`)>-1||e.match(Kt))){var r=Qn(e.split(` `),{skipLookups:!0});return{prefix:r.prefix||W(),iconName:U(r.prefix,r.iconName)||r.iconName}}if(typeof e==`string`){var i=W();return{prefix:i,iconName:U(i,e)||e}}}},library:lr,findIconDefinition:cr,toHtml:Cn},ur=function(){var e=(arguments.length>0&&arguments[0]!==void 0?arguments[0]:{}).autoReplaceSvgRoot,t=e===void 0?k:e;(Object.keys(V.styles).length>0||I.autoFetchSvg)&&A&&I.autoReplaceSvg&&Y.dom.i2svg({node:t})};function dr(e,t){return Object.defineProperty(e,`abstract`,{get:t}),Object.defineProperty(e,`html`,{get:function(){return e.abstract.map(function(e){return Cn(e)})}}),Object.defineProperty(e,`node`,{get:function(){if(A){var t=k.createElement(`div`);return t.innerHTML=e.html,t.children}}}),e}function fr(e){var t=e.children,n=e.main,r=e.mask,i=e.attributes,a=e.styles,o=e.transform;if(dn(o)&&n.found&&!r.found){var s={x:n.width/n.height/2,y:.5};i.style=un(C(C({},a),{},{"transform-origin":`${s.x+o.x/16}em ${s.y+o.y/16}em`}))}return[{tag:`svg`,attributes:i,children:t}]}function pr(e){var t=e.prefix,n=e.iconName,r=e.children,i=e.attributes,a=e.symbol,o=a===!0?`${t}-${I.cssPrefix}-${n}`:a;return[{tag:`svg`,attributes:{style:`display: none;`},children:[{tag:`symbol`,attributes:C(C({},i),{},{id:o}),children:r}]}]}function mr(e){return[`aria-label`,`aria-labelledby`,`title`,`role`].some(function(t){return t in e})}function hr(e){var t=e.icons,n=t.main,r=t.mask,i=e.prefix,a=e.iconName,o=e.transform,s=e.symbol,c=e.maskId,l=e.extra,u=e.watchable,d=u===void 0?!1:u,f=r.found?r:n,p=f.width,m=f.height,h=[I.replacementClass,a?`${I.cssPrefix}-${a}`:``].filter(function(e){return l.classes.indexOf(e)===-1}).filter(function(e){return e!==``||!!e}).concat(l.classes).join(` `),g={children:[],attributes:C(C({},l.attributes),{},{"data-prefix":i,"data-icon":a,class:h,role:l.attributes.role||`img`,viewBox:`0 0 ${p} ${m}`})};!mr(l.attributes)&&!l.attributes[`aria-hidden`]&&(g.attributes[`aria-hidden`]=`true`),d&&(g.attributes[N]=``);var _=C(C({},g),{},{prefix:i,iconName:a,main:n,mask:r,maskId:c,transform:o,symbol:s,styles:C({},l.styles)}),v=r.found&&n.found?J(`generateAbstractMask`,_)||{children:[],attributes:{}}:J(`generateAbstractIcon`,_)||{children:[],attributes:{}},y=v.children,b=v.attributes;return _.children=y,_.attributes=b,s?pr(_):fr(_)}function gr(e){var t=e.content,n=e.width,r=e.height,i=e.transform,a=e.extra,o=e.watchable,s=o===void 0?!1:o,c=C(C({},a.attributes),{},{class:a.classes.join(` `)});s&&(c[N]=``);var l=C({},a.styles);dn(i)&&(l.transform=pn({transform:i,startCentered:!0,width:n,height:r}),l[`-webkit-transform`]=l.transform);var u=un(l);u.length>0&&(c.style=u);var d=[];return d.push({tag:`span`,attributes:c,children:[t]}),d}function _r(e){var t=e.content,n=e.extra,r=C(C({},n.attributes),{},{class:n.classes.join(` `)}),i=un(n.styles);i.length>0&&(r.style=i);var a=[];return a.push({tag:`span`,attributes:r,children:[t]}),a}var vr=V.styles;function yr(e){var t=e[0],n=e[1],r=re(e.slice(4),1)[0],i=null;return i=Array.isArray(r)?{tag:`g`,attributes:{class:`${I.cssPrefix}-${Xt.GROUP}`},children:[{tag:`path`,attributes:{class:`${I.cssPrefix}-${Xt.SECONDARY}`,fill:`currentColor`,d:r[0]}},{tag:`path`,attributes:{class:`${I.cssPrefix}-${Xt.PRIMARY}`,fill:`currentColor`,d:r[1]}}]}:{tag:`path`,attributes:{fill:`currentColor`,d:r}},{found:!0,width:t,height:n,icon:i}}var br={found:!1,width:512,height:512};function xr(e,t){!Lt&&!I.showMissingIcons&&e&&console.error(`Icon with name "${e}" and prefix "${t}" is missing.`)}function Sr(e,t){var n=t;return t===`fa`&&I.styleDefault!==null&&(t=W()),new Promise(function(r,i){if(n===`fa`){var a=Wn(e)||{};e=a.iconName||e,t=a.prefix||t}if(e&&t&&vr[t]&&vr[t][e]){var o=vr[t][e];return r(yr(o))}xr(e,t),r(C(C({},br),{},{icon:I.showMissingIcons&&e&&J(`missingIconAbstract`)||{}}))})}var Cr=function(){},wr=I.measurePerformance&&pe&&pe.mark&&pe.measure?pe:{mark:Cr,measure:Cr},Tr=`FA "7.1.0"`,Er=function(e){return wr.mark(`${Tr} ${e} begins`),function(){return Dr(e)}},Dr=function(e){wr.mark(`${Tr} ${e} ends`),wr.measure(`${Tr} ${e}`,`${Tr} ${e} begins`,`${Tr} ${e} ends`)},Or={begin:Er,end:Dr},kr=function(){};function Ar(e){return typeof(e.getAttribute?e.getAttribute(N):null)==`string`}function jr(e){var t=e.getAttribute?e.getAttribute(jt):null,n=e.getAttribute?e.getAttribute(Mt):null;return t&&n}function Mr(e){return e&&e.classList&&e.classList.contains&&e.classList.contains(I.replacementClass)}function Nr(){return I.autoReplaceSvg===!0?Rr.replace:Rr[I.autoReplaceSvg]||Rr.replace}function Pr(e){return k.createElementNS(`http://www.w3.org/2000/svg`,e)}function Fr(e){return k.createElement(e)}function Ir(e){var t=(arguments.length>1&&arguments[1]!==void 0?arguments[1]:{}).ceFn,n=t===void 0?e.tag===`svg`?Pr:Fr:t;if(typeof e==`string`)return k.createTextNode(e);var r=n(e.tag);return Object.keys(e.attributes||[]).forEach(function(t){r.setAttribute(t,e.attributes[t])}),(e.children||[]).forEach(function(e){r.appendChild(Ir(e,{ceFn:n}))}),r}function Lr(e){var t=` ${e.outerHTML} `;return t=`${t}Font Awesome fontawesome.com `,t}var Rr={replace:function(e){var t=e[0];if(t.parentNode)if(e[1].forEach(function(e){t.parentNode.insertBefore(Ir(e),t)}),t.getAttribute(N)===null&&I.keepOriginalSource){var n=k.createComment(Lr(t));t.parentNode.replaceChild(n,t)}else t.remove()},nest:function(e){var t=e[0],n=e[1];if(~sn(t).indexOf(I.replacementClass))return Rr.replace(e);var r=RegExp(`${I.cssPrefix}-.*`);if(delete n[0].attributes.id,n[0].attributes.class){var i=n[0].attributes.class.split(` `).reduce(function(e,t){return t===I.replacementClass||t.match(r)?e.toSvg.push(t):e.toNode.push(t),e},{toNode:[],toSvg:[]});n[0].attributes.class=i.toSvg.join(` `),i.toNode.length===0?t.removeAttribute(`class`):t.setAttribute(`class`,i.toNode.join(` `))}var a=n.map(function(e){return Cn(e)}).join(`
`);t.setAttribute(N,``),t.innerHTML=a}};function zr(e){e()}function Br(e,t){var n=typeof t==`function`?t:kr;if(e.length===0)n();else{var r=zr;I.mutateApproach===Pt&&(r=O.requestAnimationFrame||zr),r(function(){var t=Nr(),r=Or.begin(`mutate`);e.map(t),r(),n()})}}var Vr=!1;function Hr(){Vr=!0}function Ur(){Vr=!1}var Wr=null;function Gr(e){if(fe&&I.observeMutations){var t=e.treeCallback,n=t===void 0?kr:t,r=e.nodeCallback,i=r===void 0?kr:r,a=e.pseudoElementsCallback,o=a===void 0?kr:a,s=e.observeMutationsRoot,c=s===void 0?k:s;Wr=new fe(function(e){if(!Vr){var t=W();z(e).forEach(function(e){if(e.type===`childList`&&e.addedNodes.length>0&&!Ar(e.addedNodes[0])&&(I.searchPseudoElements&&o(e.target),n(e.target)),e.type===`attributes`&&e.target.parentNode&&I.searchPseudoElements&&o([e.target],!0),e.type===`attributes`&&Ar(e.target)&&~Yt.indexOf(e.attributeName))if(e.attributeName===`class`&&jr(e.target)){var r=Qn(sn(e.target)),a=r.prefix,s=r.iconName;e.target.setAttribute(jt,a||t),s&&e.target.setAttribute(Mt,s)}else Mr(e.target)&&i(e.target)})}}),A&&Wr.observe(c,{childList:!0,attributes:!0,characterData:!0,subtree:!0})}}function Kr(){Wr&&Wr.disconnect()}function qr(e){var t=e.getAttribute(`style`),n=[];return t&&(n=t.split(`;`).reduce(function(e,t){var n=t.split(`:`),r=n[0],i=n.slice(1);return r&&i.length>0&&(e[r]=i.join(`:`).trim()),e},{})),n}function Jr(e){var t=e.getAttribute(`data-prefix`),n=e.getAttribute(`data-icon`),r=e.innerText===void 0?``:e.innerText.trim(),i=Qn(sn(e));return i.prefix||=W(),t&&n&&(i.prefix=t,i.iconName=n),i.iconName&&i.prefix?i:(i.prefix&&r.length>0&&(i.iconName=Un(i.prefix,e.innerText)||Hn(i.prefix,Dn(e.innerText))),!i.iconName&&I.autoFetchSvg&&e.firstChild&&e.firstChild.nodeType===Node.TEXT_NODE&&(i.iconName=e.firstChild.data),i)}function Yr(e){return z(e.attributes).reduce(function(e,t){return e.name!==`class`&&e.name!==`style`&&(e[t.name]=t.value),e},{})}function Xr(){return{iconName:null,prefix:null,transform:R,symbol:!1,mask:{iconName:null,prefix:null,rest:[]},maskId:null,extra:{classes:[],styles:{},attributes:{}}}}function Zr(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{styleParser:!0},n=Jr(e),r=n.iconName,i=n.prefix,a=n.rest,o=Yr(e),s=sr(`parseNodeAttributes`,{},e);return C({iconName:r,prefix:i,transform:R,mask:{iconName:null,prefix:null,rest:[]},maskId:null,symbol:!1,extra:{classes:a,styles:t.styleParser?qr(e):[],attributes:o}},s)}var Qr=V.styles;function $r(e){var t=I.autoReplaceSvg===`nest`?Zr(e,{styleParser:!1}):Zr(e);return~t.extra.classes.indexOf(qt)?J(`generateLayersText`,e,t):J(`generateSvgReplacementMutation`,e,t)}function ei(){return[].concat(w(st),w(bt))}function ti(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:null;if(!A)return Promise.resolve();var n=k.documentElement.classList,r=function(e){return n.add(`${Nt}-${e}`)},i=function(e){return n.remove(`${Nt}-${e}`)},a=I.autoFetchSvg?ei():be.concat(Object.keys(Qr));a.includes(`fa`)||a.push(`fa`);var o=[`.${qt}:not([${N}])`].concat(a.map(function(e){return`.${e}:not([${N}])`})).join(`, `);if(o.length===0)return Promise.resolve();var s=[];try{s=z(e.querySelectorAll(o))}catch{}if(s.length>0)r(`pending`),i(`complete`);else return Promise.resolve();var c=Or.begin(`onTree`),l=s.reduce(function(e,t){try{var n=$r(t);n&&e.push(n)}catch(e){Lt||e.name===`MissingIcon`&&console.error(e)}return e},[]);return new Promise(function(e,n){Promise.all(l).then(function(n){Br(n,function(){r(`active`),r(`complete`),i(`pending`),typeof t==`function`&&t(),c(),e()})}).catch(function(e){c(),n(e)})})}function ni(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:null;$r(e).then(function(e){e&&Br([e],t)})}function ri(e){return function(t){var n=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},r=(t||{}).icon?t:cr(t||{}),i=n.mask;return i&&=(i||{}).icon?i:cr(i||{}),e(r,C(C({},n),{},{mask:i}))}}var ii=function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},n=t.transform,r=n===void 0?R:n,i=t.symbol,a=i===void 0?!1:i,o=t.mask,s=o===void 0?null:o,c=t.maskId,l=c===void 0?null:c,u=t.classes,d=u===void 0?[]:u,f=t.attributes,p=f===void 0?{}:f,m=t.styles,h=m===void 0?{}:m;if(e){var g=e.prefix,_=e.iconName,v=e.icon;return dr(C({type:`icon`},e),function(){return q(`beforeDOMElementCreation`,{iconDefinition:e,params:t}),hr({icons:{main:yr(v),mask:s?yr(s.icon):{found:!1,width:null,height:null,icon:{}}},prefix:g,iconName:_,transform:C(C({},R),r),symbol:a,maskId:l,extra:{attributes:p,styles:h,classes:d}})})}},ai={mixout:function(){return{icon:ri(ii)}},hooks:function(){return{mutationObserverCallbacks:function(e){return e.treeCallback=ti,e.nodeCallback=ni,e}}},provides:function(e){e.i2svg=function(e){var t=e.node,n=t===void 0?k:t,r=e.callback;return ti(n,r===void 0?function(){}:r)},e.generateSvgReplacementMutation=function(e,t){var n=t.iconName,r=t.prefix,i=t.transform,a=t.symbol,o=t.mask,s=t.maskId,c=t.extra;return new Promise(function(t,l){Promise.all([Sr(n,r),o.iconName?Sr(o.iconName,o.prefix):Promise.resolve({found:!1,width:512,height:512,icon:{}})]).then(function(o){var l=re(o,2),u=l[0],d=l[1];t([e,hr({icons:{main:u,mask:d},prefix:r,iconName:n,transform:i,symbol:a,maskId:s,extra:c,watchable:!0})])}).catch(l)})},e.generateAbstractIcon=function(e){var t=e.children,n=e.attributes,r=e.main,i=e.transform,a=e.styles,o=un(a);o.length>0&&(n.style=o);var s;return dn(i)&&(s=J(`generateAbstractTransformGrouping`,{main:r,transform:i,containerWidth:r.width,iconWidth:r.width})),t.push(s||r.icon),{children:t,attributes:n}}}},oi={mixout:function(){return{layer:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},n=t.classes,r=n===void 0?[]:n;return dr({type:`layer`},function(){q(`beforeDOMElementCreation`,{assembler:e,params:t});var n=[];return e(function(e){Array.isArray(e)?e.map(function(e){n=n.concat(e.abstract)}):n=n.concat(e.abstract)}),[{tag:`span`,attributes:{class:[`${I.cssPrefix}-layers`].concat(w(r)).join(` `)},children:n}]})}}}},si={mixout:function(){return{counter:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},n=t.title,r=n===void 0?null:n,i=t.classes,a=i===void 0?[]:i,o=t.attributes,s=o===void 0?{}:o,c=t.styles,l=c===void 0?{}:c;return dr({type:`counter`,content:e},function(){return q(`beforeDOMElementCreation`,{content:e,params:t}),_r({content:e.toString(),title:r,extra:{attributes:s,styles:l,classes:[`${I.cssPrefix}-layers-counter`].concat(w(a))}})})}}}},ci={mixout:function(){return{text:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},n=t.transform,r=n===void 0?R:n,i=t.classes,a=i===void 0?[]:i,o=t.attributes,s=o===void 0?{}:o,c=t.styles,l=c===void 0?{}:c;return dr({type:`text`,content:e},function(){return q(`beforeDOMElementCreation`,{content:e,params:t}),gr({content:e,transform:C(C({},R),r),extra:{attributes:s,styles:l,classes:[`${I.cssPrefix}-layers-text`].concat(w(a))}})})}}},provides:function(e){e.generateLayersText=function(e,t){var n=t.transform,r=t.extra,i=null,a=null;if(me){var o=parseInt(getComputedStyle(e).fontSize,10),s=e.getBoundingClientRect();i=s.width/o,a=s.height/o}return Promise.resolve([e,gr({content:e.innerHTML,width:i,height:a,transform:n,extra:r,watchable:!0})])}}},li=RegExp(`"`,`ug`),ui=[1105920,1112319],di=C(C(C(C({},{FontAwesome:{normal:`fas`,400:`fas`}}),it),Tt),dt),fi=Object.keys(di).reduce(function(e,t){return e[t.toLowerCase()]=di[t],e},{}),pi=Object.keys(fi).reduce(function(e,t){var n=fi[t];return e[t]=n[900]||w(Object.entries(n))[0][1],e},{});function mi(e){return Dn(w(e.replace(li,``))[0]||``)}function hi(e){var t=e.getPropertyValue(`font-feature-settings`).includes(`ss01`),n=e.getPropertyValue(`content`).replace(li,``),r=n.codePointAt(0),i=r>=ui[0]&&r<=ui[1],a=n.length===2?n[0]===n[1]:!1;return i||a||t}function gi(e,t){var n=e.replace(/^['"]|['"]$/g,``).toLowerCase(),r=parseInt(t),i=isNaN(r)?`normal`:r;return(fi[n]||{})[i]||pi[n]}function _i(e,t){var n=`${At}${t.replace(`:`,`-`)}`;return new Promise(function(r,i){if(e.getAttribute(n)!==null)return r();var a=z(e.children).filter(function(e){return e.getAttribute(kt)===t})[0],o=O.getComputedStyle(e,t),s=o.getPropertyValue(`font-family`),c=s.match(Jt),l=o.getPropertyValue(`font-weight`),u=o.getPropertyValue(`content`);if(a&&!c)return e.removeChild(a),r();if(c&&u!==`none`&&u!==``){var d=o.getPropertyValue(`content`),f=gi(s,l),p=mi(d),m=c[0].startsWith(`FontAwesome`),h=hi(o),g=Hn(f,p),_=g;if(m){var v=Gn(p);v.iconName&&v.prefix&&(g=v.iconName,f=v.prefix)}if(g&&!h&&(!a||a.getAttribute(jt)!==f||a.getAttribute(Mt)!==_)){e.setAttribute(n,_),a&&e.removeChild(a);var y=Xr(),b=y.extra;b.attributes[kt]=t,Sr(g,f).then(function(i){var a=hr(C(C({},y),{},{icons:{main:i,mask:Kn()},prefix:f,iconName:_,extra:b,watchable:!0})),o=k.createElementNS(`http://www.w3.org/2000/svg`,`svg`);t===`::before`?e.insertBefore(o,e.firstChild):e.appendChild(o),o.outerHTML=a.map(function(e){return Cn(e)}).join(`
`),e.removeAttribute(n),r()}).catch(i)}else r()}else r()})}function vi(e){return Promise.all([_i(e,`::before`),_i(e,`::after`)])}function yi(e){return e.parentNode!==document.head&&!~Ft.indexOf(e.tagName.toUpperCase())&&!e.getAttribute(kt)&&(!e.parentNode||e.parentNode.tagName!==`svg`)}var bi=function(e){return!!e&&It.some(function(t){return e.includes(t)})},xi=function(e){if(!e)return[];var t=new Set,n=e.split(/,(?![^()]*\))/).map(function(e){return e.trim()});n=n.flatMap(function(e){return e.includes(`(`)?e:e.split(`,`).map(function(e){return e.trim()})});var r=y(n),i;try{for(r.s();!(i=r.n()).done;){var a=i.value;if(bi(a)){var o=It.reduce(function(e,t){return e.replace(t,``)},a);o!==``&&o!==`*`&&t.add(o)}}}catch(e){r.e(e)}finally{r.f()}return t};function Si(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:!1;if(A){var n;if(t)n=e;else if(I.searchPseudoElementsFullScan)n=e.querySelectorAll(`*`);else{var r=new Set,i=y(document.styleSheets),a;try{for(i.s();!(a=i.n()).done;){var o=a.value;try{var s=y(o.cssRules),c;try{for(s.s();!(c=s.n()).done;){var l=c.value,u=y(xi(l.selectorText)),d;try{for(u.s();!(d=u.n()).done;){var f=d.value;r.add(f)}}catch(e){u.e(e)}finally{u.f()}}}catch(e){s.e(e)}finally{s.f()}}catch(e){I.searchPseudoElementsWarnings&&console.warn(`Font Awesome: cannot parse stylesheet: ${o.href} (${e.message})
If it declares any Font Awesome CSS pseudo-elements, they will not be rendered as SVG icons. Add crossorigin="anonymous" to the <link>, enable searchPseudoElementsFullScan for slower but more thorough DOM parsing, or suppress this warning by setting searchPseudoElementsWarnings to false.`)}}}catch(e){i.e(e)}finally{i.f()}if(!r.size)return;var p=Array.from(r).join(`, `);try{n=e.querySelectorAll(p)}catch{}}return new Promise(function(e,t){var r=z(n).filter(yi).map(vi),i=Or.begin(`searchPseudoElements`);Hr(),Promise.all(r).then(function(){i(),Ur(),e()}).catch(function(){i(),Ur(),t()})})}}var Ci={hooks:function(){return{mutationObserverCallbacks:function(e){return e.pseudoElementsCallback=Si,e}}},provides:function(e){e.pseudoElements2svg=function(e){var t=e.node,n=t===void 0?k:t;I.searchPseudoElements&&Si(n)}}},wi=!1,Ti={mixout:function(){return{dom:{unwatch:function(){Hr(),wi=!0}}}},hooks:function(){return{bootstrap:function(){Gr(sr(`mutationObserverCallbacks`,{}))},noAuto:function(){Kr()},watch:function(e){var t=e.observeMutationsRoot;wi?Ur():Gr(sr(`mutationObserverCallbacks`,{observeMutationsRoot:t}))}}}},Ei=function(e){return e.toLowerCase().split(` `).reduce(function(e,t){var n=t.toLowerCase().split(`-`),r=n[0],i=n.slice(1).join(`-`);if(r&&i===`h`)return e.flipX=!0,e;if(r&&i===`v`)return e.flipY=!0,e;if(i=parseFloat(i),isNaN(i))return e;switch(r){case`grow`:e.size+=i;break;case`shrink`:e.size-=i;break;case`left`:e.x-=i;break;case`right`:e.x+=i;break;case`up`:e.y-=i;break;case`down`:e.y+=i;break;case`rotate`:e.rotate+=i;break}return e},{size:16,x:0,y:0,flipX:!1,flipY:!1,rotate:0})},Di={mixout:function(){return{parse:{transform:function(e){return Ei(e)}}}},hooks:function(){return{parseNodeAttributes:function(e,t){var n=t.getAttribute(`data-fa-transform`);return n&&(e.transform=Ei(n)),e}}},provides:function(e){e.generateAbstractTransformGrouping=function(e){var t=e.main,n=e.transform,r=e.containerWidth,i=e.iconWidth,a={outer:{transform:`translate(${r/2} 256)`},inner:{transform:`${`translate(${n.x*32}, ${n.y*32}) `} ${`scale(${n.size/16*(n.flipX?-1:1)}, ${n.size/16*(n.flipY?-1:1)}) `} ${`rotate(${n.rotate} 0 0)`}`},path:{transform:`translate(${i/2*-1} -256)`}};return{tag:`g`,attributes:C({},a.outer),children:[{tag:`g`,attributes:C({},a.inner),children:[{tag:t.icon.tag,children:t.icon.children,attributes:C(C({},t.icon.attributes),a.path)}]}]}}}},Oi={x:0,y:0,width:`100%`,height:`100%`};function ki(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:!0;return e.attributes&&(e.attributes.fill||t)&&(e.attributes.fill=`black`),e}function Ai(e){return e.tag===`g`?e.children:[e]}or([vn,ai,oi,si,ci,Ci,Ti,Di,{hooks:function(){return{parseNodeAttributes:function(e,t){var n=t.getAttribute(`data-fa-mask`),r=n?Qn(n.split(` `).map(function(e){return e.trim()})):Kn();return r.prefix||=W(),e.mask=r,e.maskId=t.getAttribute(`data-fa-mask-id`),e}}},provides:function(e){e.generateAbstractMask=function(e){var t=e.children,n=e.attributes,r=e.main,i=e.mask,a=e.maskId,o=e.transform,s=r.width,c=r.icon,l=i.width,u=i.icon,d=fn({transform:o,containerWidth:l,iconWidth:s}),f={tag:`rect`,attributes:C(C({},Oi),{},{fill:`white`})},p=c.children?{children:c.children.map(ki)}:{},m={tag:`g`,attributes:C({},d.inner),children:[ki(C({tag:c.tag,attributes:C(C({},c.attributes),d.path)},p))]},h={tag:`g`,attributes:C({},d.outer),children:[m]},g=`mask-${a||on()}`,_=`clip-${a||on()}`,v={tag:`mask`,attributes:C(C({},Oi),{},{id:g,maskUnits:`userSpaceOnUse`,maskContentUnits:`userSpaceOnUse`}),children:[f,h]},y={tag:`defs`,children:[{tag:`clipPath`,attributes:{id:_},children:Ai(u)},v]};return t.push(y,{tag:`rect`,attributes:C({fill:`currentColor`,"clip-path":`url(#${_})`,mask:`url(#${g})`},Oi)}),{children:t,attributes:n}}}},{provides:function(e){var t=!1;O.matchMedia&&(t=O.matchMedia(`(prefers-reduced-motion: reduce)`).matches),e.missingIconAbstract=function(){var e=[],n={fill:`currentColor`},r={attributeType:`XML`,repeatCount:`indefinite`,dur:`2s`};e.push({tag:`path`,attributes:C(C({},n),{},{d:`M156.5,447.7l-12.6,29.5c-18.7-9.5-35.9-21.2-51.5-34.9l22.7-22.7C127.6,430.5,141.5,440,156.5,447.7z M40.6,272H8.5 c1.4,21.2,5.4,41.7,11.7,61.1L50,321.2C45.1,305.5,41.8,289,40.6,272z M40.6,240c1.4-18.8,5.2-37,11.1-54.1l-29.5-12.6 C14.7,194.3,10,216.7,8.5,240H40.6z M64.3,156.5c7.8-14.9,17.2-28.8,28.1-41.5L69.7,92.3c-13.7,15.6-25.5,32.8-34.9,51.5 L64.3,156.5z M397,419.6c-13.9,12-29.4,22.3-46.1,30.4l11.9,29.8c20.7-9.9,39.8-22.6,56.9-37.6L397,419.6z M115,92.4 c13.9-12,29.4-22.3,46.1-30.4l-11.9-29.8c-20.7,9.9-39.8,22.6-56.8,37.6L115,92.4z M447.7,355.5c-7.8,14.9-17.2,28.8-28.1,41.5 l22.7,22.7c13.7-15.6,25.5-32.9,34.9-51.5L447.7,355.5z M471.4,272c-1.4,18.8-5.2,37-11.1,54.1l29.5,12.6 c7.5-21.1,12.2-43.5,13.6-66.8H471.4z M321.2,462c-15.7,5-32.2,8.2-49.2,9.4v32.1c21.2-1.4,41.7-5.4,61.1-11.7L321.2,462z M240,471.4c-18.8-1.4-37-5.2-54.1-11.1l-12.6,29.5c21.1,7.5,43.5,12.2,66.8,13.6V471.4z M462,190.8c5,15.7,8.2,32.2,9.4,49.2h32.1 c-1.4-21.2-5.4-41.7-11.7-61.1L462,190.8z M92.4,397c-12-13.9-22.3-29.4-30.4-46.1l-29.8,11.9c9.9,20.7,22.6,39.8,37.6,56.9 L92.4,397z M272,40.6c18.8,1.4,36.9,5.2,54.1,11.1l12.6-29.5C317.7,14.7,295.3,10,272,8.5V40.6z M190.8,50 c15.7-5,32.2-8.2,49.2-9.4V8.5c-21.2,1.4-41.7,5.4-61.1,11.7L190.8,50z M442.3,92.3L419.6,115c12,13.9,22.3,29.4,30.5,46.1 l29.8-11.9C470,128.5,457.3,109.4,442.3,92.3z M397,92.4l22.7-22.7c-15.6-13.7-32.8-25.5-51.5-34.9l-12.6,29.5 C370.4,72.1,384.4,81.5,397,92.4z`})});var i=C(C({},r),{},{attributeName:`opacity`}),a={tag:`circle`,attributes:C(C({},n),{},{cx:`256`,cy:`364`,r:`28`}),children:[]};return t||a.children.push({tag:`animate`,attributes:C(C({},r),{},{attributeName:`r`,values:`28;14;28;28;14;28;`})},{tag:`animate`,attributes:C(C({},i),{},{values:`1;0;1;1;0;1;`})}),e.push(a),e.push({tag:`path`,attributes:C(C({},n),{},{opacity:`1`,d:`M263.7,312h-16c-6.6,0-12-5.4-12-12c0-71,77.4-63.9,77.4-107.8c0-20-17.8-40.2-57.4-40.2c-29.1,0-44.3,9.6-59.2,28.7 c-3.9,5-11.1,6-16.2,2.4l-13.1-9.2c-5.6-3.9-6.9-11.8-2.6-17.2c21.2-27.2,46.4-44.7,91.2-44.7c52.3,0,97.4,29.8,97.4,80.2 c0,67.6-77.4,63.5-77.4,107.8C275.7,306.6,270.3,312,263.7,312z`}),children:t?[]:[{tag:`animate`,attributes:C(C({},i),{},{values:`1;0;0;0;0;1;`})}]}),t||e.push({tag:`path`,attributes:C(C({},n),{},{opacity:`0`,d:`M232.5,134.5l7,168c0.3,6.4,5.6,11.5,12,11.5h9c6.4,0,11.7-5.1,12-11.5l7-168c0.3-6.8-5.2-12.5-12-12.5h-23 C237.7,122,232.2,127.7,232.5,134.5z`}),children:[{tag:`animate`,attributes:C(C({},i),{},{values:`0;0;1;1;0;0;`})}]}),{tag:`g`,attributes:{class:`missing`},children:e}}}},{hooks:function(){return{parseNodeAttributes:function(e,t){var n=t.getAttribute(`data-fa-symbol`);return e.symbol=n===null?!1:n===``?!0:n,e}}}}],{mixoutsTo:Y}),Y.noAuto;var ji=Y.config;Y.library,Y.dom;var Mi=Y.parse;Y.findIconDefinition,Y.toHtml;var Ni=Y.icon;Y.layer,Y.text,Y.counter;var Pi=c(u(),1),Fi=c(f(),1);function Ii(e){return e-=0,e===e}function Li(e){return Ii(e)?e:(e=e.replace(/[_-]+(.)?/g,(e,t)=>t?t.toUpperCase():``),e.charAt(0).toLowerCase()+e.slice(1))}function Ri(e){return e.charAt(0).toUpperCase()+e.slice(1)}var X=new Map,zi=1e3;function Bi(e){if(X.has(e))return X.get(e);let t={},n=0,r=e.length;for(;n<r;){let i=e.indexOf(`;`,n),a=i===-1?r:i,o=e.slice(n,a).trim();if(o){let e=o.indexOf(`:`);if(e>0){let n=o.slice(0,e).trim(),r=o.slice(e+1).trim();if(n&&r){let e=Li(n);t[e.startsWith(`webkit`)?Ri(e):e]=r}}}n=a+1}if(X.size===zi){let e=X.keys().next().value;e&&X.delete(e)}return X.set(e,t),t}function Vi(e,t,n={}){if(typeof t==`string`)return t;let r=(t.children||[]).map(t=>Vi(e,t)),i=t.attributes||{},a={};for(let[e,t]of Object.entries(i))switch(!0){case e===`class`:a.className=t;break;case e===`style`:a.style=Bi(String(t));break;case e.startsWith(`aria-`):case e.startsWith(`data-`):a[e.toLowerCase()]=t;break;default:a[Li(e)]=t}let{style:o,role:s,"aria-label":c,...l}=n;return o&&(a.style=a.style?{...a.style,...o}:o),s&&(a.role=s),c&&(a[`aria-label`]=c,a[`aria-hidden`]=`false`),e(t.tag,{...l,...a},...r)}var Hi=Vi.bind(null,Pi.createElement),Ui=(e,t)=>{let n=(0,Pi.useId)();return e||(t?n:void 0)},Wi=class{constructor(e=`react-fontawesome`){this.enabled=!1;let t=!1;try{t=typeof process<`u`&&!1}catch{}this.scope=e,this.enabled=t}log(...e){this.enabled&&console.log(`[${this.scope}]`,...e)}warn(...e){this.enabled&&console.warn(`[${this.scope}]`,...e)}error(...e){this.enabled&&console.error(`[${this.scope}]`,...e)}};typeof process<`u`&&{}.FA_VERSION;var Gi=`searchPseudoElementsFullScan`in ji?`7.0.0`:`6.0.0`,Ki=Number.parseInt(Gi)>=7,Z=`fa`,Q={beat:`fa-beat`,fade:`fa-fade`,beatFade:`fa-beat-fade`,bounce:`fa-bounce`,shake:`fa-shake`,spin:`fa-spin`,spinPulse:`fa-spin-pulse`,spinReverse:`fa-spin-reverse`,pulse:`fa-pulse`},qi={left:`fa-pull-left`,right:`fa-pull-right`},Ji={90:`fa-rotate-90`,180:`fa-rotate-180`,270:`fa-rotate-270`},Yi={"2xs":`fa-2xs`,xs:`fa-xs`,sm:`fa-sm`,lg:`fa-lg`,xl:`fa-xl`,"2xl":`fa-2xl`,"1x":`fa-1x`,"2x":`fa-2x`,"3x":`fa-3x`,"4x":`fa-4x`,"5x":`fa-5x`,"6x":`fa-6x`,"7x":`fa-7x`,"8x":`fa-8x`,"9x":`fa-9x`,"10x":`fa-10x`},$={border:`fa-border`,fixedWidth:`fa-fw`,flip:`fa-flip`,flipHorizontal:`fa-flip-horizontal`,flipVertical:`fa-flip-vertical`,inverse:`fa-inverse`,rotateBy:`fa-rotate-by`,swapOpacity:`fa-swap-opacity`,widthAuto:`fa-width-auto`},Xi={default:`fa-layers`};function Zi(e){let t=ji.cssPrefix||ji.familyPrefix||Z;return t===Z?e:e.replace(new RegExp(String.raw`(?<=^|\s)${Z}-`,`g`),`${t}-`)}function Qi(e){let{beat:t,fade:n,beatFade:r,bounce:i,shake:a,spin:o,spinPulse:s,spinReverse:c,pulse:l,fixedWidth:u,inverse:d,border:f,flip:p,size:m,rotation:h,pull:g,swapOpacity:_,rotateBy:v,widthAuto:y,className:b}=e,x=[];return b&&x.push(...b.split(` `)),t&&x.push(Q.beat),n&&x.push(Q.fade),r&&x.push(Q.beatFade),i&&x.push(Q.bounce),a&&x.push(Q.shake),o&&x.push(Q.spin),c&&x.push(Q.spinReverse),s&&x.push(Q.spinPulse),l&&x.push(Q.pulse),u&&x.push($.fixedWidth),d&&x.push($.inverse),f&&x.push($.border),p===!0&&x.push($.flip),(p===`horizontal`||p===`both`)&&x.push($.flipHorizontal),(p===`vertical`||p===`both`)&&x.push($.flipVertical),m!=null&&x.push(Yi[m]),h!=null&&h!==0&&x.push(Ji[h]),g!=null&&x.push(qi[g]),_&&x.push($.swapOpacity),Ki?(v&&x.push($.rotateBy),y&&x.push($.widthAuto),(ji.cssPrefix||ji.familyPrefix||Z)===Z?x:x.map(Zi)):x}var $i=e=>typeof e==`object`&&`icon`in e&&!!e.icon;function ea(e){if(e)return $i(e)?e:Mi.icon(e)}function ta(e){return Object.keys(e)}var na=new Wi(`FontAwesomeIcon`),ra={border:!1,className:``,mask:void 0,maskId:void 0,fixedWidth:!1,inverse:!1,flip:!1,icon:void 0,listItem:!1,pull:void 0,pulse:!1,rotation:void 0,rotateBy:!1,size:void 0,spin:!1,spinPulse:!1,spinReverse:!1,beat:!1,fade:!1,beatFade:!1,bounce:!1,shake:!1,symbol:!1,title:``,titleId:void 0,transform:void 0,swapOpacity:!1,widthAuto:!1},ia=new Set(Object.keys(ra)),aa=Pi.forwardRef((e,t)=>{let n={...ra,...e},{icon:r,mask:i,symbol:a,title:o,titleId:s,maskId:c,transform:l}=n,u=Ui(c,!!i),d=Ui(s,!!o),f=ea(r);if(!f)return na.error(`Icon lookup is undefined`,r),null;let p=Qi(n),m=typeof l==`string`?Mi.transform(l):l,h=ea(i),g=Ni(f,{...p.length>0&&{classes:p},...m&&{transform:m},...h&&{mask:h},symbol:a,title:o,titleId:d,maskId:u});if(!g)return na.error(`Could not find icon`,f),null;let{abstract:_}=g,v={ref:t};for(let e of ta(n))ia.has(e)||(v[e]=n[e]);return Hi(_[0],v)});aa.displayName=`FontAwesomeIcon`,`${Xi.default}${$.fixedWidth}`;function oa({variant:e=`action`,icon:t,iconClassName:n=`text-sm`,children:r,className:i=``,disabled:a,type:o=`button`,...s}){return(0,Fi.jsxs)(`button`,{type:o,className:`flex items-center justify-center transition-all duration-50 ease-in-out rounded font-medium ${a?`cursor-not-allowed opacity-50`:`cursor-pointer`} ${{primary:`
      px-3 py-1.5 text-sm shadow-md
      bg-btn-primary dark:bg-btn-primary-dark
      text-btn-primary-text dark:text-btn-primary-text-dark
      hover:bg-btn-primary-hover dark:hover:bg-btn-primary-hover-dark
  `,secondary:`
      px-3 py-1.5 text-sm border
      bg-btn-secondary dark:bg-btn-secondary-dark
      text-btn-secondary-text dark:text-btn-secondary-text-dark
      border-btn-secondary-border dark:border-btn-secondary-border-dark
      hover:bg-btn-secondary-hover dark:hover:bg-btn-secondary-hover-dark
      hover:text-btn-secondary-text-hover dark:hover:text-btn-secondary-text-hover-dark
      hover:border-btn-secondary-border-hover dark:hover:border-btn-secondary-border-hover-dark
      active:bg-btn-secondary-active dark:active:bg-btn-secondary-active-dark
      active:text-btn-secondary-text-active dark:active:text-btn-secondary-text-active-dark
      active:border-btn-secondary-border-active dark:active:border-btn-secondary-border-active-dark
      transition-all duration-200
  `,action:`
      p-1 border text-xs
      bg-btn-secondary dark:bg-btn-secondary-dark
      hover:bg-btn-secondary-hover dark:hover:bg-btn-secondary-hover-dark
      text-btn-primary dark:text-btn-primary-dark
      hover:text-btn-primary-hover dark:hover:text-btn-primary-hover-dark
      border-btn-secondary dark:border-btn-secondary-dark
      hover:border-btn-secondary-border-hover dark:hover:border-btn-secondary-border-hover-dark
  `,ghost:`
      p-1 px-2 py-2
      text-text-primary dark:text-text-primary-dark
      hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark
      hover:bg-bg-primary-hover dark:hover:bg-bg-primary-hover-dark
  `,danger:`
      px-3 py-1.5 text-sm border bg-transparent
      text-btn-danger-outline border-btn-danger-outline-border
      hover:bg-btn-danger-outline-hover-bg
      hover:text-btn-danger-outline-hover-text
      hover:border-btn-danger-outline-hover-border

      dark:text-btn-danger-outline-dark
      dark:border-btn-danger-outline-border-dark
      dark:hover:bg-btn-danger-outline-hover-bg-dark
      dark:hover:text-btn-danger-outline-hover-text-dark
      dark:hover:border-btn-danger-outline-hover-border-dark

      disabled:bg-btn-disabled-bg disabled:text-btn-disabled-text
      disabled:border-transparent disabled:opacity-100

      dark:disabled:bg-btn-disabled-bg-dark
      dark:disabled:text-btn-disabled-text-dark
      dark:disabled:border-transparent
  `}[e]} ${i}`.replace(/\s+/g,` `).trim(),disabled:a,...s,children:[t&&(0,Fi.jsx)(aa,{icon:t,className:n}),r&&(0,Fi.jsx)(`span`,{className:t?`ml-1`:``,children:r})]})}export{o as a,u as i,aa as n,c as o,f as r,oa as t};