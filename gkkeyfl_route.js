// ===== GK KeyFL: trang dang nhap cho ung dung desktop =====
// 1) Dan hang KEYFL_PAGE nay vao cung cho voi cac hang so khac (vi du ngay duoi ham `api`).
// 2) Trong `export default { async fetch(...) }`, ngay truoc dong:
//        const lang = pickLang(url);
//    them:
//        if (pathname === '/acc/gkkeyfl') return new Response(KEYFL_PAGE, { headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' } });
//
// Trang nay dung lai /api/login, /api/register, /api/google co san. Dang nhap xong no chuyen
// trinh duyet ve http://127.0.0.1:<port>/cb (chi cong local do ung dung tu mo) kem ten + email.
const KEYFL_PAGE = String.raw`<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Đăng nhập GK KeyFL</title>
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#07070b;color:#fff;font-family:Inter,system-ui,sans-serif;
background-image:radial-gradient(60vmax 60vmax at 20% 20%,rgba(124,58,237,.35),transparent),radial-gradient(50vmax 50vmax at 85% 80%,rgba(219,39,119,.25),transparent)}
.card{width:min(420px,92vw);background:#0b0b0f;border:1px solid rgba(255,255,255,.1);border-radius:28px;padding:36px 32px;box-shadow:0 20px 80px rgba(124,58,237,.25)}
h1{margin:0 0 6px;font-size:26px}p.s{margin:0 0 22px;color:#8d8d9a;font-size:14px}
#g{display:flex;justify-content:center;min-height:44px;margin-bottom:6px}
.or{display:flex;align-items:center;gap:12px;color:#6b6b78;font-size:12px;margin:14px 0}.or:before,.or:after{content:"";flex:1;height:1px;background:rgba(255,255,255,.1)}
input{width:100%;height:50px;margin-bottom:10px;padding:0 18px;border-radius:25px;border:1px solid rgba(255,255,255,.14);background:#15151b;color:#fff;font-size:15px;outline:none}
input:focus{border-color:#7a2bff}
button{width:100%;height:50px;border:0;border-radius:25px;background:#fff;color:#0b0b0f;font-weight:700;font-size:15px;cursor:pointer}
button:disabled{opacity:.6}a{color:#a56bff;cursor:pointer;text-decoration:none}.sw{text-align:center;font-size:13px;margin:16px 0 0;color:#8d8d9a}
#err{color:#ff7a8a;font-size:13px;min-height:18px;margin:10px 0 0;text-align:center}
</style></head><body><div class="card">
<h1>GK KeyFL</h1><p class="s" id="sub">Đăng nhập để tiếp tục</p>
<div id="g"></div><div class="or">hoặc</div>
<form id="f" autocomplete="on"><input id="name" placeholder="Tên hiển thị" maxlength="40" style="display:none">
<input id="email" type="email" placeholder="Email" required autocomplete="email">
<input id="pw" type="password" placeholder="Mật khẩu (từ 8 ký tự)" required autocomplete="current-password">
<button id="go">Đăng nhập</button></form>
<p class="sw"><a id="swap">Chưa có tài khoản? Đăng ký</a></p><p id="err"></p></div>
<script>
var Q=new URLSearchParams(location.search),port=Q.get('port')||'',state=Q.get('state')||'';
var valid=/^[0-9]{4,5}$/.test(port)&&+port>=1024&&+port<=65535&&/^[A-Za-z0-9_-]{8,64}$/.test(state);
var reg=false,$=function(i){return document.getElementById(i)};
function err(m){$('err').textContent=m||''}
if(!valid)err('Liên kết không hợp lệ. Hãy mở lại từ ứng dụng GK KeyFL.');
function done(u){
  if(!valid)return;
  $('sub').textContent='Đang quay lại ứng dụng…';
  location.href='http://127.0.0.1:'+port+'/cb?state='+encodeURIComponent(state)+'&name='+encodeURIComponent(u.name||'')+'&email='+encodeURIComponent(u.email||'');
}
function post(path,body){
  return fetch(path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.error||'Lỗi');return j})});
}
$('swap').onclick=function(){reg=!reg;$('name').style.display=reg?'':'none';$('go').textContent=reg?'Tạo tài khoản':'Đăng nhập';
  $('swap').textContent=reg?'Đã có tài khoản? Đăng nhập':'Chưa có tài khoản? Đăng ký';$('pw').autocomplete=reg?'new-password':'current-password';err('')};
$('f').onsubmit=function(e){e.preventDefault();err('');$('go').disabled=true;
  var b={email:$('email').value,password:$('pw').value};if(reg)b.name=$('name').value;
  post(reg?'/api/register':'/api/login',b).then(function(j){done(j.user)}).catch(function(x){err(x.message);$('go').disabled=false})};
fetch('/api/config').then(function(r){return r.json()}).then(function(c){
  if(!c.google){$('g').style.display='none';return}
  var s=document.createElement('script');s.src='https://accounts.google.com/gsi/client';s.async=true;
  s.onload=function(){google.accounts.id.initialize({client_id:c.google,callback:function(r){
    post('/api/google',{credential:r.credential}).then(function(j){done(j.user)}).catch(function(x){err(x.message)})}});
    google.accounts.id.renderButton($('g'),{theme:'filled_black',size:'large',shape:'pill',width:320,text:'continue_with'})};
  document.head.appendChild(s)}).catch(function(){$('g').style.display='none'});
</script></body></html>`;
