(function () {
  function advance(state, action, stops, now = Date.now()) {
    const next = {...state, timers: {...state.timers}}
    if (action === 'restart') {
      return {index:0, resetCount:state.resetCount+1, timers:{act1:0,interval:0,act2:0}, running:false, hasStarted:false}
    }
    if (action === 'clock' || (action === 'next' && !state.hasStarted)) {
      if (stops[state.index].phase !== 'finished') {
        next.running = !state.running
        next.hasStarted = true
        next.startedAt ??= now
      }
      return next
    }
    next.index = Math.max(0, Math.min(stops.length-1, state.index+(action==='next' ? 1 : -1)))
    if (stops[next.index].phase === 'finished') {
      next.running = false
      if (next.startedAt && !next.endedAt) next.endedAt = Math.max(now,next.startedAt)
    }
    return next
  }
  if (typeof module !== 'undefined') module.exports = advance
  else window.advanceShow = advance
})()
