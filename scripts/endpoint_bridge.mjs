/** Native export bridge: use the app's exact renderers, endpoint rows and CSV encoding. */
import {readFileSync,writeFileSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const [operation,requestPath]=process.argv.slice(2);
const request=JSON.parse(readFileSync(requestPath,'utf8'));
const moduleAt=name=>import(pathToFileURL(join(resolve(request.site_directory),'dist',name)));
const audit=await moduleAt('endpoint-audit.mjs');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');

if(operation==='render'){
  let source,live,noise;
  const {synthesize}=await moduleAt('synthesis.mjs');
  const {prepareSource,renderSource}=await moduleAt('source-audio.mjs');
  if(request.mode==='drone'){
    live=JSON.parse(readFileSync(join(request.site_directory,'dist/data/live.json')));
    const bytes=readFileSync(join(request.site_directory,'dist',live.noise.url));
    if(hash(bytes)!==live.noise.sha256)throw new Error('Frozen noise asset failed checksum verification.');
    const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
    noise=Float64Array.from({length:bytes.byteLength/8},(_,i)=>view.getFloat64(i*8,true));
    request.base_id='drone-'+hash(JSON.stringify(live));
    request.batch_id='native:'+audit.droneAuditId(request.base_id,request.assumed_spl_db)+':'+request.run_id;
  }else{
    const bytes=readFileSync(request.samples_file),view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
    source=prepareSource(Float64Array.from({length:bytes.byteLength/8},(_,i)=>view.getFloat64(i*8,true)),request.metadata);
    request.base_id=request.metadata.source_id;
    request.batch_id='native:'+audit.auditId(request.metadata,request.assumed_spl_db)+':'+request.run_id;
  }
  const reports=audit.endpointConditions().map((condition,index)=>{
    const result=request.mode==='drone'?synthesize(condition.selection,live,noise):renderSource(condition.selection,source);
    result.sha256_wav=hash(new Uint8Array(result.wav));
    const wavPath=join(request.work_directory,String(index).padStart(2,'0')+'.wav');
    writeFileSync(wavPath,new Uint8Array(result.wav));
    const {samples,wav,plots,...metadata}=result;
    return {condition,stimulus:metadata,wav_path:wavPath};
  });
  writeFileSync(request.reports_file,JSON.stringify({base_id:request.base_id,batch_id:request.batch_id,reports}));
}else if(operation==='csv'){
  const {reports,base_id,batch_id}=JSON.parse(readFileSync(request.reports_file));
  const models=JSON.parse(readFileSync(request.models_file));
  const rows=audit.withReferenceChanges(reports.map((report,index)=>({
    ...audit.measurementRow({condition:report.condition,stimulus:report.stimulus,model:models[index],batchId:batch_id,assumedSplDb:request.assumed_spl_db,createdAt:request.created_at,baseId:base_id}),
    analysis_backend:'native-cpython',export_run_id:request.run_id,source_decode_json:JSON.stringify(request.decode||null),
  })));
  writeFileSync(request.csv_file,audit.rowsToCsv(rows));
}else throw new Error('Unknown endpoint bridge operation.');
