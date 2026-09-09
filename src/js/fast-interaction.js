// ===== 功能：手机端持续快速轻触（每一次 UI 交互都走 touchend 快路径） =====
(function () {
  var d = window.mochiDevice || {};
  if (!d.isMobile && !d.isTablet) return;
  if (!('ontouchstart' in window) && !(navigator.maxTouchPoints > 0)) return;

  var st = null;
  var ghostUntil = 0;
  var ghostTarget = null;
  var MAX_MS = 320;
  var MAX_MOVE2 = 100; // 10px：超过即视为滑动，绝不拦原生滚动

  function actionable(el) {
    if (!el || !el.closest) return null;
    var a = el.closest('button, a[href], [role="button"], .tab, [data-page], [data-action], [onclick]');
    if (!a) return null;
    // 原生输入/选择/编辑/拖拽控件保留浏览器默认触摸链，避免破坏键盘、picker、滑块、上传。
    if (a.matches('input, textarea, select, option, label, [contenteditable="true"]')) return null;
    if (a.closest('input, textarea, select, [contenteditable="true"]')) return null;
    if (a.disabled || a.getAttribute('aria-disabled') === 'true') return null;
    if (a.draggable || a.getAttribute('draggable') === 'true') return null;
    return a;
  }

  document.addEventListener('touchstart', function (e) {
    try {
      if (!e.touches || e.touches.length !== 1) { st = null; return; }
      var t = e.touches[0], a = actionable(e.target);
      st = a ? { a:a, x:t.clientX, y:t.clientY, at:Date.now(), moved:false } : null;
    } catch (x) { st = null; }
  }, { passive:true, capture:true });

  document.addEventListener('touchmove', function (e) {
    if (!st || !e.touches || e.touches.length !== 1) return;
    var t = e.touches[0], dx = t.clientX - st.x, dy = t.clientY - st.y;
    if (dx * dx + dy * dy > MAX_MOVE2) st.moved = true;
  }, { passive:true, capture:true });

  document.addEventListener('touchcancel', function () { st = null; }, { passive:true, capture:true });

  document.addEventListener('touchend', function (e) {
    try {
      var s = st; st = null;
      if (!s || s.moved || Date.now() - s.at > MAX_MS) return;
      if (!e.changedTouches || e.changedTouches.length !== 1) return;
      var t = e.changedTouches[0], dx = t.clientX - s.x, dy = t.clientY - s.y;
      if (dx * dx + dy * dy > MAX_MOVE2) return;
      var hit = document.elementFromPoint ? document.elementFromPoint(t.clientX, t.clientY) : e.target;
      var a = actionable(hit || e.target);
      if (!a || a !== s.a) return;

      // touchend 已确认是轻点：立即执行一次 click，并阻止浏览器稍后再合成第二次 click。
      // preventDefault 只发生在“已结束且零位移的可点击 UI”上，不进入 touchmove，故页面滚动
      // 和左右/上下滑动保持原生 compositor 快路径；每次轻点都重新判定，不是一次性优化。
      e.preventDefault();
      ghostTarget = a;
      ghostUntil = Date.now() + 700;
      a.click();
    } catch (x) {}
  }, { passive:false });

  // 个别 WebKit 壳即便 touchend preventDefault 仍可能补发兼容 click；只吞同目标的幽灵点击。
  document.addEventListener('click', function (e) {
    if (!ghostTarget || Date.now() > ghostUntil) { ghostTarget = null; return; }
    if (e.isTrusted && (e.target === ghostTarget || (ghostTarget.contains && ghostTarget.contains(e.target)))) {
      e.preventDefault();
      e.stopImmediatePropagation();
      ghostTarget = null;
    }
  }, { capture:true });
})();
