(function(){
var D={
en:{
skip:"Skip to the tool",tagline:"Paste a link. Get the file.",sub:"Free, no sign-up. Up to 1080p, or audio only.",
label:"Video link",ph:"Paste a link from YouTube, TikTok, Instagram…",paste:"Paste",check:"Check link",clear:"Clear",
platforms:"Works with YouTube, TikTok, Instagram, Facebook, X, Threads, LinkedIn and RedNote.",
flow:"Copy a link, paste it here, save the file.",
analyzing:"Checking your link…",analyzingSub:"This usually takes a few seconds.",cancel:"Cancel",
video:"Video",audio:"Audio",quality:"Quality",best:"Best",std:"128 kbps",
dlVideo:"Download video",dlAudio:"Download audio",dling:"Downloading",cancelDl:"Cancel download",
doneT:"Ready to save",save:"Save to device",saved:"Saved to your device",another:"Download another link",
errInvalidT:"That isn't a link",errInvalidB:"Paste the full address, starting with https://.",
errUnsupT:"This site isn't supported yet",errUnsupB:"Try a link from YouTube, TikTok, Instagram, Facebook, X, Threads, LinkedIn or RedNote.",
errNetT:"Couldn't reach the server",errNetB:"Check your connection, then try again.",
btnOther:"Paste another link",btnRetry:"Try again",
ready:"Ready",failed:"Failed",queue:"This session",
listT:"Playlist · 12 videos",listAll:"Download all (12)",listMore:"Show all 12 videos",rowDl:"Download",rowDone:"Saved",
histT:"Recent downloads",again:"Download again",histNote:"Kept on this device only.",
aboutT:"About Vidrop",howT:"How it works",s1:"Copy the link of a video or photo.",s2:"Paste it above, then pick video or audio and a quality.",s3:"Tap Download, then Save to device.",
whyT:"Why Vidrop",why:"Free, no account, up to 1080p, whole playlists in one go.",
faqT:"Questions",q1:"Where are my files saved?",a1:"On your device. On a phone, tap Save to device when the download finishes.",
q2:"Is it really free?",a2:"Yes. No account and no limits.",q3:"Can I download a whole playlist?",a3:"Yes. Paste a YouTube playlist or channel link, then pick the videos.",
q4:"Why did my link fail?",a4:"Private or deleted posts can't be downloaded. Make sure the post is public, then try again.",
terms:"Terms of use",by:"By Quang",demo:"Preview state",langLabel:"Tiếng Việt",
t1:"How to fold a paper boat in 60 seconds",t2:"Street food tour: night market",t3:"Pasta in 10 minutes",t4:"Desk setup, small room",
m1:"YouTube · 2:47",menu:"History",dropIt:"Drop the link.",ex:"Tap a site to see which links work.",
sizeNote:"Origami_paper_boat.mp4 · 18 MB"},
vi:{
skip:"Bỏ qua tới công cụ",tagline:"Dán link. Nhận file.",sub:"Miễn phí, không cần đăng ký. Tối đa 1080p hoặc chỉ lấy âm thanh.",
label:"Link video",ph:"Dán link từ YouTube, TikTok, Instagram…",paste:"Dán",check:"Kiểm tra link",clear:"Xoá",
platforms:"Hỗ trợ YouTube, TikTok, Instagram, Facebook, X, Threads, LinkedIn và RedNote.",
flow:"Sao chép link, dán vào đây, lưu file.",
analyzing:"Đang kiểm tra link…",analyzingSub:"Thường chỉ mất vài giây.",cancel:"Huỷ",
video:"Video",audio:"Âm thanh",quality:"Chất lượng",best:"Tốt nhất",std:"128 kbps",
dlVideo:"Tải video",dlAudio:"Tải âm thanh",dling:"Đang tải",cancelDl:"Huỷ tải",
doneT:"Đã tải xong",save:"Lưu vào thiết bị",saved:"Đã lưu vào thiết bị",another:"Tải link khác",
errInvalidT:"Đây chưa phải là link",errInvalidB:"Dán đầy đủ địa chỉ, bắt đầu bằng https://.",
errUnsupT:"Chưa hỗ trợ trang này",errUnsupB:"Hãy thử link từ YouTube, TikTok, Instagram, Facebook, X, Threads, LinkedIn hoặc RedNote.",
errNetT:"Không kết nối được máy chủ",errNetB:"Kiểm tra mạng rồi thử lại.",
btnOther:"Dán link khác",btnRetry:"Thử lại",
ready:"Sẵn sàng",failed:"Lỗi",queue:"Phiên này",
listT:"Danh sách phát · 12 video",listAll:"Tải tất cả (12)",listMore:"Xem cả 12 video",rowDl:"Tải",rowDone:"Đã lưu",
histT:"Tải gần đây",again:"Tải lại",histNote:"Chỉ lưu trên thiết bị này.",
aboutT:"Giới thiệu Vidrop",howT:"Cách dùng",s1:"Sao chép link của video hoặc ảnh.",s2:"Dán vào ô phía trên, rồi chọn video hay âm thanh và chất lượng.",s3:"Bấm Tải, sau đó Lưu vào thiết bị.",
whyT:"Vì sao chọn Vidrop",why:"Miễn phí, không cần tài khoản, tối đa 1080p, tải cả danh sách phát một lần.",
faqT:"Câu hỏi thường gặp",q1:"File được lưu ở đâu?",a1:"Trên thiết bị của bạn. Với điện thoại, bấm Lưu vào thiết bị khi tải xong.",
q2:"Có thật sự miễn phí không?",a2:"Có. Không cần tài khoản, không giới hạn.",q3:"Có tải được cả danh sách phát không?",a3:"Có. Dán link danh sách phát hoặc kênh YouTube, rồi chọn các video cần tải.",
q4:"Vì sao link của tôi lỗi?",a4:"Bài riêng tư hoặc đã xoá thì không tải được. Hãy kiểm tra bài đăng ở chế độ công khai rồi thử lại.",
terms:"Điều khoản sử dụng",by:"Bởi Quang",demo:"Xem trước trạng thái",langLabel:"English",
t1:"How to fold a paper boat in 60 seconds",t2:"Street food tour: night market",t3:"Pasta in 10 minutes",t4:"Desk setup, small room",
m1:"YouTube · 2:47",menu:"Lịch sử",dropIt:"Thả link vào.",ex:"Chạm vào một trang để xem link nào dùng được.",
sizeNote:"Origami_paper_boat.mp4 · 18 MB"}};
var IC={
clip:'<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
dl:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
check:'<path d="M20 6 9 17l-5-5"/>',x:'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
alert:'<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
play:'<polygon points="6 3 20 12 6 21 6 3" fill="currentColor"/>',
music:'<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
film:'<rect width="18" height="18" x="3" y="3" rx="2"/><path d="m10 8 6 4-6 4Z"/>',
hist:'<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
refresh:'<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
chev:'<path d="m6 9 6 6 6-6"/>',arrow:'<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',spin:'<path d="M21 12a9 9 0 1 1-6.219-8.56"/>'};
var $=function(s){return document.querySelector(s)},$$=function(s){return Array.prototype.slice.call(document.querySelectorAll(s))};
var qs=new URLSearchParams(location.search);
var lang=qs.get('lang')||((navigator.language||'').slice(0,2)==='vi'?'vi':'en');
var state='empty',errKind='invalid',kind='video',pct=64,timer=null,tm=null;
var SAMPLE='https://www.youtube.com/watch?v=jNQXAC9IVRw';
var SUPPORTED=/(youtube\.com|youtu\.be|tiktok\.com|instagram\.com|facebook\.com|fb\.watch|x\.com|twitter\.com|threads\.(com|net)|linkedin\.com|rednote\.com|xiaohongshu\.com)/i;
function t(k){return D[lang][k]}
function icons(){$$('[data-icon]').forEach(function(e){if(e.dataset.done)return;e.dataset.done=1;e.innerHTML='<svg viewBox="0 0 24 24" width="'+(e.dataset.size||20)+'" height="'+(e.dataset.size||20)+'" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'+IC[e.dataset.icon]+'</svg>'})}
function rowHTML(title,meta,label,done,idx){return '<li class="row"><span class="thumb sm" aria-hidden="true"></span>'+(idx?'<span class="idx" aria-hidden="true">'+idx+'</span>':'')+'<span class="rt"><b>'+title+'</b><small>'+meta+'</small></span><button type="button" class="rbtn'+(done?' is-done':'')+'">'+label+'</button></li>'}
function renderLists(){
var h=$('#hist'),p=$('#plist');
if(h)h.innerHTML=rowHTML(t('t1'),'YouTube · 2:47',t('again'))+rowHTML(t('t2'),'TikTok · 0:48',t('again'))+rowHTML(t('t3'),'Instagram · 1:05',t('again'));
if(p)p.innerHTML=rowHTML(t('t1'),'2:47',t('rowDone'),true,'01')+rowHTML(t('t2'),'8:12',t('rowDl'),false,'02')+rowHTML(t('t3'),'10:03',t('rowDl'),false,'03')+rowHTML(t('t4'),'4:31',t('rowDl'),false,'04');
$$('.rbtn.is-done').forEach(function(b){b.insertAdjacentHTML('afterbegin','<span data-icon="check" data-size="16"></span>')});
icons()}
function renderQ(){
var q=$('#qopts');if(!q)return;
var o=kind==='video'?[['best',t('best')],['1080','1080p'],['720','720p'],['480','480p']]:[['best',t('best')],['128',t('std')]];
q.innerHTML=o.map(function(x,i){return '<label class="opt"><input type="radio" name="q" value="'+x[0]+'"'+(i===0?' checked':'')+'><span>'+x[1]+'</span></label>'}).join('')}
function errText(){var k={invalid:['errInvalidT','errInvalidB','btnOther'],unsupported:['errUnsupT','errUnsupB','btnOther'],network:['errNetT','errNetB','btnRetry']}[errKind];
$('#errT').textContent=t(k[0]);$('#errB').textContent=t(k[1]);$('#retry').firstChild&&0;var r=$('#retryLbl');if(r)r.textContent=t(k[2])}
function setProgress(){$$('.pct').forEach(function(e){e.textContent=pct+'%'});$$('.bar-fill').forEach(function(e){e.style.width=pct+'%'});$$('[role=progressbar]').forEach(function(e){e.setAttribute('aria-valuenow',pct)})}
function render(){
document.body.dataset.state=state;document.body.dataset.err=errKind;
$$('[data-s]').forEach(function(e){e.hidden=e.dataset.s.split(' ').indexOf(state)<0});
var u=$('#url');
if(u){u.readOnly=state==='analyzing';
 if(state==='empty'){}
 else if(state==='error'){if(errKind==='invalid'&&!/^https?:/.test(u.value))u.value=u.value||'hello world'}
 else if(!u.value||!/^https?:/.test(u.value))u.value=SAMPLE;
 u.setAttribute('aria-invalid',state==='error'&&errKind!=='network'?'true':'false');
 u.setAttribute('aria-describedby',state==='error'?'errB':'');}
var c=$('#check');if(c)c.disabled=state==='analyzing';
errText();setProgress();
var dl=$('#dlLbl');if(dl)dl.textContent=kind==='video'?t('dlVideo'):t('dlAudio');
var d=$('#demo');if(d)d.value=state==='error'?'error-'+errKind:state;
var sv=$('#save');if(sv&&state!=='done')sv.dataset.saved='';
var sl=$('#saveLbl');if(sl)sl.textContent=sv&&sv.dataset.saved?t('saved'):t('save')}
function apply(){
document.documentElement.lang=lang;
$$('[data-i]').forEach(function(e){e.textContent=t(e.dataset.i)});
$$('[data-ph]').forEach(function(e){e.placeholder=t(e.dataset.ph)});
$$('[data-al]').forEach(function(e){e.setAttribute('aria-label',t(e.dataset.al))});
var l=$('#lang');if(l){l.textContent=lang==='en'?'VI':'EN';l.setAttribute('aria-label',t('langLabel'))}
$$('.sizeNote').forEach(function(e){e.textContent=t('sizeNote')});
renderQ();renderLists();render();icons()}
function stop(){clearInterval(timer);clearTimeout(tm)}
function go(s,ek){stop();state=s;if(ek)errKind=ek;if(s==='empty'){var u=$('#url');if(u)u.value=''}
if(s==='downloading'&&!timer&&pct>=100)pct=64;render()}
function check(){
var u=$('#url'),v=(u.value||'').trim();stop();
if(!/^https?:\/\/\S+\.\S+/i.test(v)){errKind='invalid';state='error';render();return}
if(!SUPPORTED.test(v)){errKind='unsupported';state='error';render();return}
if(/offline/i.test(v)){errKind='network';state='error';render();return}
state='analyzing';render();tm=setTimeout(function(){state=/playlist|list=/i.test(v)?'list':'result';render()},1600)}
function startDl(){stop();pct=0;state='downloading';render();
timer=setInterval(function(){pct=Math.min(100,pct+Math.ceil(Math.random()*8));setProgress();if(pct>=100){stop();state='done';render()}},140)}
function init(){
var f=$('#f');
if(f)f.addEventListener('submit',function(e){e.preventDefault();check()});
var p=$('#paste');if(p)p.addEventListener('click',function(){
 var fill=function(v){$('#url').value=v||SAMPLE;check()};
 if(navigator.clipboard&&navigator.clipboard.readText){navigator.clipboard.readText().then(function(v){fill(/^https?:/.test(v)?v:SAMPLE)},function(){fill(SAMPLE)})}else fill(SAMPLE)});
var l=$('#lang');if(l)l.addEventListener('click',function(){lang=lang==='en'?'vi':'en';apply()});
$$('input[name=kind]').forEach(function(r){r.addEventListener('change',function(){kind=r.value;renderQ();render()})});
function on(id,fn){var e=$(id);if(e)e.addEventListener('click',fn)}
on('#cancelA',function(){go('empty')});on('#dl',startDl);on('#cancelD',function(){go('result')});
on('#another',function(){go('empty');var u=$('#url');if(u)u.focus()});
on('#retry',function(){if(errKind==='network'){$('#url').value=$('#url').value||SAMPLE;check()}else{go('empty');$('#url').focus()}});
on('#clear',function(){go('empty');$('#url').focus()});
on('#save',function(){this.dataset.saved='1';render()});
var d=$('#demo');if(d)d.addEventListener('change',function(){var v=d.value;stop();if(v.indexOf('error-')===0){errKind=v.slice(6);state='error'}else state=v;if(v==='downloading')pct=64;if(v==='empty'){var u=$('#url');if(u)u.value=''}if(v==='list'){$('#url').value='https://www.youtube.com/playlist?list=PLboat'}else if(v!=='empty'&&v.indexOf('error')!==0){$('#url').value=SAMPLE}if(v==='error-unsupported')$('#url').value='https://example.com/clip';if(v==='error-invalid')$('#url').value='hello world';render()});
if(qs.has('bare')){var dm=$('#demoBar');if(dm)dm.hidden=true}
var s0=qs.get('s');
if(s0){if(s0.indexOf('error-')===0){errKind=s0.slice(6);state='error'}else state=s0;
 var u=$('#url');
 if(s0==='list')u.value='https://www.youtube.com/playlist?list=PLboat';
 else if(s0==='error-invalid')u.value='hello world';
 else if(s0==='error-unsupported')u.value='https://example.com/clip';
 else if(s0!=='empty')u.value=SAMPLE;
 if(s0==='downloading')pct=64}
apply()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
