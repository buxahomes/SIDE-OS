#!/usr/bin/env python3
"""Public-metric account discovery, bounded requests, encrypted research export."""
import json, os, subprocess, tempfile, time
from pathlib import Path
from datetime import timedelta
from side_radar import ROOT, TZ, datetime, ENDPOINTS, post_json, RadarError
KEYWORDS = ['女友视角','沉浸式男友','男生vlog','约会男友','北京约会']
def main():
    key=os.environ.get('REDFOX_API_KEY','').strip()
    if not key:
        print('missing_configuration');return 1
    now=datetime.now(TZ)
    report={'generated_at':now.isoformat(),'purpose':'account_discovery_public_metrics',
            'run_url':'https://github.com/buxahomes/SIDE-OS/actions/runs/'+os.environ.get('GITHUB_RUN_ID',''),
            'queries':[],'errors':[],'analysis_status':'not_requested','date_window':[(now.date()-timedelta(days=89)).isoformat(),now.date().isoformat()]}
    for platform,(url,header,list_key,source) in ENDPOINTS.items():
        for keyword in KEYWORDS:
            q={'platform':platform,'keyword':keyword,'page':1,'page_size':50,'endpoint':url}
            payload={'keyword':keyword,'pageNum':1,'pageSize':50,'source':source,
                     'startDate':report['date_window'][0],'endDate':report['date_window'][1]}
            try:
                data=post_json(url,{header:key},payload)
                q['code']=data.get('code')
                if data.get('code')!=2000:
                    q['status']='provider_error';report['errors'].append({'platform':platform,'keyword':keyword,'code':data.get('code')})
                else:
                    q['status']='ok';q['data']=data.get('data');q['returned']=len((data.get('data') or {}).get(list_key,[]))
            except RadarError as exc:
                q['status']='error';q['error']=str(exc);report['errors'].append({'platform':platform,'keyword':keyword,'error':str(exc)})
            report['queries'].append(q)
            if q.get('code')==3201:break
            time.sleep(.3)
    report['account_queries']=[]
    accounts=['0zzzzyx1227','Cy_1866','xh20001209','31439131211','47856230192','pclrAyouyou']
    tasks=[('works',a,'https://redfox.hk/story/api/dy/data/listWorkByAccount',{'uniqueName':a,'pageNum':1,'pageSize':50,'source':'抖音作品爬取'}) for a in accounts]
    tasks.append(('diagnosis','成帅real/蛋黄酥油','https://redfox.hk/story/api/dyUser/queryData',{'accountNames':['成帅real','蛋黄酥油'],'source':'抖音账号诊断-GitHub'}))
    for kind,a,url,payload in tasks:
        q={'kind':kind,'account':a,'endpoint':url,'observed_at':datetime.now(TZ).isoformat()}
        try:
            result=post_json(url,{'X-API-KEY':key},payload)
            q['code']=result.get('code');q['data']=result.get('data')
        except RadarError as exc:q['error']=str(exc)
        report['account_queries'].append(q)
        if q.get('code')==3201:break
        time.sleep(.3)
    out=Path(os.environ.get('RUNNER_TEMP',tempfile.gettempdir()))/'side-report.cms'
    with tempfile.TemporaryDirectory() as folder:
        plain=Path(folder)/'report.json';plain.write_text(json.dumps(report,ensure_ascii=False));plain.chmod(0o600)
        subprocess.run(['openssl','cms','-encrypt','-binary','-aes-256-gcm','-in',str(plain),'-out',str(out),'-outform','DER',str(ROOT/'deploy/report-recipient.pem')],check=True)
    print(json.dumps({'requests':len(report['queries']),'errors':len(report['errors']),'encrypted_report_ready':True}))
    return 0
if __name__=='__main__':raise SystemExit(main())
