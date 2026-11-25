'use strict'
const {createServer} = require('node:http')
const {readFileSync, createReadStream, mkdirSync, writeFileSync, renameSync} = require('node:fs')
const {join} = require('node:path')
const {performance} = require('node:perf_hooks')
const pageDirectory = process.env.PAGE_DIRECTORY || join(__dirname,'pdf-pages')
const scriptIndex = readFileSync(join(pageDirectory,'index.json'))
const {pages,stops,title,cues=[],fingerprint} = JSON.parse(scriptIndex)
const html = readFileSync(join(__dirname,'index.html'))
let camera = null
if (process.env.CAMERA_URL) {
  const url = new URL(process.env.CAMERA_URL)
  if (!['http:','https:'].includes(url.protocol) || url.username || url.password) {
    throw new Error('CAMERA_URL must be an HTTP(S) URL without embedded credentials.')
  }
  const mode = process.env.CAMERA_MODE || 'image'
  if (!['image','embed'].includes(mode)) throw new Error('CAMERA_MODE must be image or embed.')
  camera = {url:url.href,mode}
}
const viewers = new Set()
const characters = new Set(stops.filter(stop=>!stop.pageStop && ['act1','act2'].includes(stop.phase))
  .map(stop=>stop.speaker.trim().toUpperCase()))
function characterPath(path) {
  if (!/^\/[^/]+\/?$/.test(path)) return false
  try {
    return characters.has(decodeURIComponent(path.replace(/^\/|\/$/g,'')).trim().toUpperCase())
  } catch {
    return false
  }
}
const advance = require('./show-state')
const {createHash,randomUUID} = require('node:crypto')
const scriptId = createHash('sha256').update(fingerprint || scriptIndex).digest('hex')
const timingDirectory = process.env.TIMING_DIRECTORY || join(__dirname,'data')
mkdirSync(timingDirectory,{recursive:true})
const checkpointFile = join(timingDirectory,'show-'+scriptId+'.json')
let checkpoint
try {
  checkpoint = JSON.parse(readFileSync(checkpointFile,'utf8'))
} catch (error) {
  if (error.code !== 'ENOENT') throw error
}
const revision = checkpoint?.state.revision || randomUUID()
let state = checkpoint?.state || advance({resetCount:0}, 'restart', stops)
if (state.running) {
  state.timers[stops[state.index].phase] += Math.max(0,Date.now()-checkpoint.savedAt)
}
let since = performance.now()
function saveCheckpoint(next) {
  writeFileSync(checkpointFile+'.tmp',JSON.stringify({state:{...next,revision},savedAt:Date.now()}))
  renameSync(checkpointFile+'.tmp',checkpointFile)
}
saveCheckpoint(state)
function snapshot() {
  const timers = {...state.timers}
  if (state.running) timers[stops[state.index].phase] += performance.now()-since
  return {...state,timers,revision}
}

const timingFile = join(timingDirectory,'timings.json')
let history
try {
  history = JSON.parse(readFileSync(timingFile,'utf8'))
} catch (error) {
  if (error.code !== 'ENOENT') throw error
  history = []
}
const phases = ['act1','interval','act2']
function recordTiming(run) {
  if (stops[run.index]?.phase !== 'finished' || !Number.isInteger(run.resetCount) ||
      !Number.isFinite(run.startedAt) || !Number.isFinite(run.endedAt) ||
      run.startedAt <= 0 || run.endedAt < run.startedAt || run.endedAt > 8.64e15 ||
      !phases.every(key => Number.isFinite(run.timers?.[key]) && run.timers[key] >= 0)) return false
  const id = revision+':'+run.resetCount+':'+run.startedAt
  if (history.some(entry=>entry.id===id)) return true
  const timers = Object.fromEntries(phases.map(key=>[key,run.timers[key]]))
  const updated = [...history,{id,title,startedAt:run.startedAt,endedAt:run.endedAt,timers}]
  writeFileSync(timingFile+'.tmp',JSON.stringify(updated))
  renameSync(timingFile+'.tmp',timingFile)
  history = updated
  return true
}
const date = new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/London',dateStyle:'medium'})
const time = new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/London',timeStyle:'medium',hourCycle:'h23'})
const escape = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
function duration(ms) {
  const seconds = Math.floor(ms/1000)
  return [Math.floor(seconds/3600),Math.floor(seconds/60)%60,seconds%60].map(n=>String(n).padStart(2,'0')).join(':')
}
function timingsPage() {
  const count = history.length
  const averages = count
    ? Object.fromEntries(phases.map(key=>[key,history.reduce((sum,entry)=>sum+entry.timers[key],0)/count]))
    : null
  const totalOf = entry => phases.reduce((total,key)=>total+entry.timers[key],0)
  const cell = (key,value) => {
    let html = duration(value)
    if (count > 1) {
      const average = key === 'total' ? phases.reduce((sum,key)=>sum+averages[key],0) : averages[key]
      const diff = value - average
      html += ' <small class="'+(diff<=0?'ahead':'behind')+'">'+(diff<=0?'−':'+')+duration(Math.abs(diff))+'</small>'
    }
    return '<td>'+html+'</td>'
  }
  const rows = [...history].sort((a,b)=>b.endedAt-a.endedAt).map(entry => {
    const start = date.format(entry.startedAt)
    const end = date.format(entry.endedAt)
    return '<tr><td>'+escape(entry.title)+'</td><td>'+start+'</td><td>'+time.format(entry.startedAt)+'</td><td>'
      +(start===end ? '' : end+' ')+time.format(entry.endedAt)+'</td>'
      +phases.map(key=>cell(key,entry.timers[key])).join('')+cell('total',totalOf(entry))+'</tr>'
  }).join('')
  const foot = count
    ? '<tfoot><tr><td colspan="4">Average of '+count+' run'+(count===1?'':'s')+'</td>'
      +phases.map(key=>'<td>'+duration(averages[key])+'</td>').join('')
      +'<td>'+duration(phases.reduce((sum,key)=>sum+averages[key],0))+'</td></tr></tfoot>'
    : ''
  return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Show timings</title><style>body{margin:2rem;background:#15171b;color:#f0f2f5;font:16px system-ui}a{color:#a8d1ff}section{overflow:auto}table{border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:.65rem;border-bottom:1px solid #555;white-space:nowrap}small{font-size:.75rem;font-weight:400}small.ahead{color:#7bd88a}small.behind{color:#f3cc88}tfoot td{font-weight:700;border-top:2px solid #777}</style><main><h1>Show timings</h1><p><a href="/control">Control</a> · <a href="/">Viewer</a> · <a href="/stage">Stage</a></p><p>Start and finish shown in UK time. Green = faster than average, amber = slower.</p><section><table><thead><tr>'+['Show','Date','Start','Finish','Act 1','Interval','Act 2','Total'].map(label=>'<th scope="col">'+label+'</th>').join('')+'</tr></thead><tbody>'+(rows||'<tr><td colspan="8">No completed shows yet.</td></tr>')+'</tbody>'+foot+'</table></section></main></html>'
}

function send(res) {
  res.write('data: '+JSON.stringify(snapshot())+'\n\n')
}
setInterval(() => {
  for (const res of viewers) res.write(': keepalive\n\n')
},15000).unref()

createServer(async (req,res) => {
  const path = req.url.split('?')[0]
  res.setHeader('Cache-Control','no-store')
  if (req.method === 'GET') {
    if (['/','/control','/control/','/stage','/stage/'].includes(path)) return res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}).end(html)
    if (path === '/manifest.webmanifest' || /^\/prompt-icon-(180|192|512)\.png$/.test(path)) {
      const type = path.endsWith('.png') ? 'image/png' : 'application/manifest+json'
      return res.writeHead(200,{'Content-Type':type}).end(readFileSync(join(__dirname,path.slice(1))))
    }
    if (path === '/timings') return res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}).end(timingsPage())
    if (path === '/show-state.js') return res.writeHead(200,{'Content-Type':'application/javascript'}).end(readFileSync(join(__dirname,'show-state.js')))
    if (path === '/setup') return res.writeHead(200,{'Content-Type':'application/json'}).end(JSON.stringify({pages,stops,title,camera,revision}))
    if (path === '/stage-cues') return res.writeHead(200,{'Content-Type':'application/json'}).end(JSON.stringify(cues))
    if (path === '/events') {
      res.writeHead(200,{'Content-Type':'text/event-stream','X-Accel-Buffering':'no'})
      viewers.add(res)
      res.on('close',() => viewers.delete(res))
      return send(res)
    }
    if (characterPath(path)) return res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'}).end(html)
    const image = /^\/page\/(\d+)\.png$/.exec(path)
    if (image && Number(image[1]) < pages.length) {
      res.writeHead(200,{'Content-Type':'image/png'})
      return createReadStream(join(pageDirectory,Number(image[1])+'.png')).pipe(res)
    }
  }
  if (req.method === 'POST' && ['/sync','/timings'].includes(path)) {
    if (req.headers['x-prompt-control'] !== '1') return res.writeHead(403).end()
    try {
      let body = ''
      for await (const chunk of req) {
        body += chunk
        if (body.length > 2048) return res.writeHead(413).end()
      }
      const next = JSON.parse(body)
      if (next.revision !== revision) return res.writeHead(409).end()
      if (path === '/timings') return res.writeHead(recordTiming(next) ? 204 : 400).end()
      if (!Number.isInteger(next.index) || !stops[next.index] ||
          !Number.isInteger(next.resetCount) || typeof next.running !== 'boolean' ||
          typeof next.hasStarted !== 'boolean' ||
          !['act1','interval','act2'].every(k=>Number.isFinite(next.timers?.[k]) && next.timers[k]>=0) ||
          (next.running && stops[next.index].phase === 'finished')) return res.writeHead(400).end()
      recordTiming(next)
      saveCheckpoint(next)
      state = next
      since = performance.now()
      for (const viewer of viewers) send(viewer)
      return res.writeHead(204).end()
    } catch (error) {
      if (!(error instanceof SyntaxError)) {
        console.error('Could not process prompt update:',error)
        return res.writeHead(500).end()
      }
      return res.writeHead(400).end()
    }
  }
  const command = /^\/command\/(next|back|restart|clock)$/.exec(path)
  if (req.method === 'POST' && command) {
    if (req.headers['x-prompt-control'] !== '1') return res.writeHead(403).end()
    const next = advance(snapshot(),command[1],stops)
    try {
      recordTiming(next)
      saveCheckpoint(next)
    } catch (error) {
      console.error('Could not save show timings:',error)
      return res.writeHead(500).end()
    }
    state = next
    since = performance.now()
    for (const viewer of viewers) send(viewer)
    return res.writeHead(204).end()
  }
  res.writeHead(404).end()
}).listen(Number(process.env.PORT || 3000), process.env.BIND || '0.0.0.0', function () {
  const url = 'http://localhost:'+this.address().port+'/'
  console.log('Viewer: '+url)
  console.log('Control: '+url+'control')
})
