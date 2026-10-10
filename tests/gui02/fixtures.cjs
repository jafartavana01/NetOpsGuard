/* SYNTHETIC screenshot fixtures only. Never imported by production. */
function fixtures(empty=false) {
 const now=new Date(),at=minutes=>new Date(now-minutes*60000).toISOString();
 const auth=empty?[]:[{timestamp:at(1),user:'operator1',device:'R1',outcome:'success',is_login:true,command:''},{timestamp:at(3),user:'invalid-user',device:'R6',outcome:'failure',is_login:true,command:''}];
 const decisions=empty?[]:[{timestamp:at(.2),user:'operator1',device:'R2',outcome:'success',result:'permit',is_login:false,command:'show running-config'},{timestamp:at(.8),user:'operator2',device:'R1',outcome:'failure',result:'deny',is_login:false,command:'configure terminal'},{timestamp:at(2),user:'operator1',device:'R1',outcome:'success',result:'permit',is_login:true,command:''}];
 return {
 '/api/system/status':{checked_at:now.toISOString(),database:'connected',services:{'tac-plus-ng.service':{active_state:'active'},'aaa-platform.service':{active_state:'active'}},os:'Synthetic Ubuntu preview',build_info:{commit:'synthetic-fixture',build_profile:'test fixture — not deployed'}},
 '/api/devices':empty?[]:Array.from({length:7},(_,i)=>({id:'d'+i,name:'R'+(i+1),enabled:i<6})),
 '/api/tacacs-accounting/health':{permit_count:empty?0:420,non_permit_count:empty?0:12,distinct_users:empty?0:8,hourly_activity:Array.from({length:24},(_,i)=>({hour:new Date(Math.floor(now.getTime()/3600000)*3600000-(23-i)*3600000).toISOString(),count:empty?0:[3,2,0,1,0,2,8,12,18,24,21,34,28,22,15,17,29,40,37,26,32,45,20,10][i]}))},
 '/api/tacacs-accounting/sessions':{active_count:empty?0:2,total_sessions:empty?0:2,sessions:empty?[]:[{is_active:true},{is_active:true}]},
 authentication:{counts:{success:empty?0:42,failure:empty?0:2,unknown:empty?0:1},rows:auth,kind:'authentication'},
 all:{counts:{success:empty?0:40,failure:empty?0:3,unknown:0},rows:decisions,kind:'all'},
 '/api/security/dashboard':{devices_audited:empty?0:6,average_score:empty?null:72.3,failed_checks:empty?0:64,severity_counts:empty?[]:[{severity:'critical',count:6},{severity:'high',count:12},{severity:'medium',count:46}]},
 '/api/ncm/overview':{total_devices:empty?0:6,devices_with_recent_backup:empty?0:5,devices_with_failed_backup:empty?0:1,devices_never_backed_up:empty?0:1,total_configurations:empty?0:24,configurations_changed_recently:empty?0:4,active_jobs:0,recent_changes:empty?[]:[{device_name:'R3',version_number:4,created_at:at(90)},{device_name:'R2',version_number:6,created_at:at(135)}]},
 '/api/ncm/drift':{total:empty?0:6,in_sync:empty?0:4,drifted:empty?0:1,no_baseline:empty?0:1,no_snapshot:0,baseline_gone:0,coverage_gaps:empty?0:1},
 '/api/config/candidate':{applicable:true,has_changes:false,diff:'',candidate:'',active:'',diagnostics:[],uncompilable_policies:[]},
 '/api/ad-settings/health':{success:true,message:'Synthetic connection check passed',detail:{}}
 };
}
module.exports={fixtures};
