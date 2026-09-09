#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
ma = ROOT / "src/js/mobile-adapt.js"
dv = ROOT / "src/js/device.js"

def replace_once(path, old, new, label):
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[FAIL] {label}: expected exactly 1 match in {path}, got {n}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[OK] {label}: {path}")

old_ma_judge = """  function _escJudge(streak, deadline, tapEndAt) {
    if (streak < 3) return;
    setTimeout(function () {
      try {
        if (_escLastClickAt >= tapEndAt) { _escState.streak = 0; return; } // 点击活着=误报退出
        if (_escState.streak < 3 || _escHealing) return;
"""
new_ma_judge = """  function _escJudge(streak, deadline, tapEndAt) {
    if (streak < 3) return;
    setTimeout(function () {
      try {
        if (_escLastClickAt >= tapEndAt) { _escState.streak = 0; return; } // 点击活着=误报退出
        // FIX：把高成本浮层/键盘复核移到“已经连续 3 次没有 click”之后。
        // 旧逻辑在每次正常轻点的 touchend 阶段就调用 _escAnyFloatOpen()，
        // 它会遍历全部浮层并执行 getClientRects()，可能触发同步布局；
        // iOS WebKit 必须等 touchend 监听结束后才合成 click，所以这段同步布局
        // 会直接表现为“按钮点下去停一下才响应”。正常 click 活着时走上面的
        // _escLastClickAt 快速退出，完全不再扫描浮层。
        if (_escAnyFloatOpen()) { _escState.streak = 0; return; }
        if (_escKbOpen()) { _escState.streak = 0; return; }
        if (_escState.streak < 3 || _escHealing) return;
"""

old_ma_end = """      var dx = te.clientX - tap.x, dy = te.clientY - tap.y;
      if (dx * dx + dy * dy > 144) return;    // 位移 >12px=滚动手势不算
      if (_escAnyFloatOpen()) { _escState.streak = 0; return; } // 弹层操作期不计数
      if (_escKbOpen()) { _escState.streak = 0; return; }       // 键盘会话期不计数
      var now = Date.now();
"""
new_ma_end = """      var dx = te.clientX - tap.x, dy = te.clientY - tap.y;
      if (dx * dx + dy * dy > 144) return;    // 位移 >12px=滚动手势不算
      // 浮层/键盘检查延后到 _escJudge 的“连续 3 次无 click”慢路径。
      // 这里保持 touchend 热路径纯计算，避免在浏览器合成 click 前强制布局。
      var now = Date.now();
"""

old_ring = """  const TOUCH_KEY = 'xy-home-v2:__diag-touch';
  // 通用环形缓冲写入（环境变化/长任务/网络失败/交互轨迹共用）
  function ringPush(key, ent, cap) {
    try {
      var arr = [];
      try {
        var old = localStorage.getItem(key);
        if (old) { var o = JSON.parse(old); if (Array.isArray(o)) arr = o; }
      } catch (e) {}
      arr.push(ent);
      if (arr.length > cap) arr = arr.slice(arr.length - cap);
      try { localStorage.setItem(key, JSON.stringify(arr)); } catch (e) {}
    } catch (e) {}
  }
"""
new_ring = """  const TOUCH_KEY = 'xy-home-v2:__diag-touch';
  // 通用环形缓冲写入（环境变化/长任务/网络失败/交互轨迹共用）
  // FIX：诊断事件不再在 touchstart/click/input 热路径同步 localStorage.setItem。
  // localStorage 是同步 API；iOS WebKit 会在主线程完成序列化/落盘后才能继续派发
  // 后续事件。此前每次触摸、click、输入都读+parse+写一次，即使单次不足 50ms，
  // 仍会形成可感知的“点/滑后慢半拍”，且输入越频繁越明显。
  // 现在先写内存环形缓冲，再在 idle/短延时里合并落盘；诊断内容、容量、键名均不变。
  const _diagRingMem = Object.create(null);
  const _diagRingFlush = Object.create(null);
  function _diagLoadRing(key) {
    if (_diagRingMem[key]) return _diagRingMem[key];
    var arr = [];
    try {
      var old = localStorage.getItem(key);
      if (old) {
        var o = JSON.parse(old);
        if (Array.isArray(o)) arr = o;
      }
    } catch (e) {}
    _diagRingMem[key] = arr;
    return arr;
  }
  function _diagFlushRing(key) {
    try {
      _diagRingFlush[key] = 0;
      var arr = _diagRingMem[key];
      if (arr) localStorage.setItem(key, JSON.stringify(arr));
    } catch (e) {}
  }
  function _diagScheduleFlush(key) {
    if (_diagRingFlush[key]) return;
    try {
      if (typeof window.requestIdleCallback === 'function') {
        _diagRingFlush[key] = window.requestIdleCallback(function () {
          _diagFlushRing(key);
        }, { timeout: 300 });
      } else {
        _diagRingFlush[key] = setTimeout(function () {
          _diagFlushRing(key);
        }, 80);
      }
    } catch (e) {
      _diagRingFlush[key] = setTimeout(function () {
        _diagFlushRing(key);
      }, 80);
    }
  }
  function ringPush(key, ent, cap) {
    try {
      var arr = _diagLoadRing(key);
      arr.push(ent);
      if (arr.length > cap) {
        arr.splice(0, arr.length - cap);
      }
      _diagScheduleFlush(key);
    } catch (e) {}
  }
"""

if not ma.exists() or not dv.exists():
    raise SystemExit("Please run this script from the mochi repository root (or pass the repo path).")

replace_once(ma, old_ma_judge, new_ma_judge, "defer expensive stuck-check scan")
replace_once(ma, old_ma_end, new_ma_end, "keep touchend hot path layout-free")
replace_once(dv, old_ring, new_ring, "batch diagnostic localStorage writes")

print("\nDone. Only these source files were changed:")
print("  src/js/mobile-adapt.js")
print("  src/js/device.js")
print("\nRecommended next step: run `node build.mjs` in the repo root.")
