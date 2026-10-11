/* Synthetic data only. Shapes mirror the current API serializers. */
function fixtures(){
 const device={id:'d1',name:'R1',ip_address:'192.0.2.10',enabled:true,device_group_id:'dg1',device_group_name:'edge',description:'Distribution router',vendor:'Cisco',platform:'ios',has_secret:true,has_radius_secret:false,radius_enabled:false,ipv6_address:null};
 const group={id:'g1',name:'ops',description:'Directory network operators',ad_group_name:'AAA-ops',authority:'EXTERNAL',external_source_id:'source1',external_source_name:'netopsguard_ad_source1',binding_status:'valid',binding_diagnostics:[],member_count:0,referenced_by_policy_names:['R1_ops','Edge_read']};
 const user={id:'u1',username:'operator',full_name:'Local Operator',group_id:'g2',group_name:'breakglass',enabled:true,auth_source:'local',allowed_source_ips:null};
 const set={id:'cs1',name:'Read_Only',description:'Operational show commands; exclude sensitive output',vendor:'cisco_ios',enabled:true,policy_count:2,rules:[{id:'r1',order:0,action:'deny',command_pattern:'^show running-config',description:'Sensitive config',category_id:'cat1',category_name:'Sensitive'},{id:'r2',order:1,action:'permit',command_pattern:'^show',description:'Show commands',category_id:null,category_name:null}]};
 const policy={id:'p1',name:'R1_ops',priority:10,enabled:true,description:'Directory operators on R1',default_priv_lvl:15,default_action:'deny',condition_group_id:'g1',condition_group_name:'ops',condition_device_id:'d1',condition_device_name:'R1',condition_device_group_id:null,condition_device_group_name:null,command_sets:[{id:'cs1',name:'Read_Only'}],requires_manual_approval:false,has_condition_tree:false};
 const leaf=(type,id)=>({object_type:type,operator:'equal',value:'',referenced_object_id:id});
 const tree={logical_operator:'AND',conditions:[leaf('user_group','g1')],child_groups:[{logical_operator:'OR',conditions:[leaf('device','d1'),leaf('device_group','dg1')],child_groups:[]}]};
 const records=['permit','deny','unrecognized','success'].map((result,i)=>({parsed:true,user:i===2?'unknown-user':'operator',nas:'R1',nac:'198.51.100.12',accttype:'cmd',result,cmd:['show version <cr>','show running-config <cr>','show clock','show interfaces'][i],service:'shell',timestamp:'2026-10-10T14:2'+i+':00Z',raw_line:`SYNTHETIC accounting record: ${result}`,raw_prefix:''}));
 return {
 '/api/devices':[device,{...device,id:'d2',name:'SW1',ip_address:'192.0.2.20',enabled:false}],
 '/api/device-groups':[{id:'dg1',name:'edge',description:'WAN edge devices',member_count:2}],
 '/api/device-groups/dg1/members':[device],
 '/api/tacacs-users':[user,{...user,id:'u2',username:'directory.operator',auth_source:'ad',group_id:'g1',group_name:'ops'}],
 '/api/tacacs-groups':[group,{...group,id:'g2',name:'breakglass',authority:'LEGACY',ad_group_name:null,external_source_id:null,external_source_name:null,binding_status:'legacy',member_count:1,referenced_by_policy_names:[]}],
 '/api/tacacs-groups/external-sources':[{id:'source1',name:'netopsguard_ad_source1',host:'ad.example.test',enabled:true,group_prefix:'AAA-',use_memberof:true}],
 '/api/policies':[policy,{...policy,id:'p2',name:'Edge_read',priority:20,description:'Nested device scope',has_condition_tree:true,condition_group_id:null,condition_group_name:null,condition_device_id:null,condition_device_name:null}],
 '/api/policies/p1/condition-tree':{has_migrated:false,tree:null},
 '/api/policies/p2/condition-tree':{has_migrated:true,tree},
 '/api/command-sets':[set],
 '/api/command-categories':[{id:'cat1',name:'Sensitive',vendor:'cisco_ios',risk_level:'HIGH',description:'Commands exposing configuration'}],
 '/api/tacacs-accounting':{records,matched:4,total_in_log:4},
 '/api/tacacs-accounting/sessions':{sessions:[{id:'s1',user:'operator',device:'R1',port:'tty2',source_ip:'198.51.100.12',is_active:true,start_at:'2026-10-10T14:00:00Z',stop_at:null,commands:['show version','show interfaces']},{id:'s2',user:'auditor',device:'SW1',port:'tty1',source_ip:'198.51.100.14',is_active:false,start_at:'2026-10-10T13:00:00Z',stop_at:'2026-10-10T13:12:00Z',commands:['show clock']}],total:2},
 '/api/tacacs-accounting/access-events':{rows:['success','failure','unknown'].map((outcome,i)=>({timestamp:'2026-10-10T14:00:00Z',outcome,user:['operator','directory.operator','unreadable'][i],device:'R1',source_ip:'198.51.100.12',result:['Login succeeded','Login failed','Unrecognized record'][i],command:'',kind:'authentication'})),counts:{success:1,failure:1,unknown:1},matched:3,total_in_log:3,source_note:'Synthetic access events'},
 '/api/tacacs-logs/access':{lines:['SYNTHETIC access log — use Access Events for parsed authentication outcomes.']},
 '/api/policy-simulator/evaluate':{authentication:{result:'NOT_CHECKED',detail:'No password supplied'},identity:{username:'operator',found:true,group_name:'breakglass'},authorization:{matched_policy_name:'R1_ops',priv_lvl:15,command_decision:'permit'},trace:[{matched:true,description:'Stored device condition matched'},{matched:null,description:'Advisory fixture; native authorization not tested'}]},
 '/api/effective-access/user/u1':{subject_type:'user',subject_name:'operator',devices:[{device_name:'R1',matched_policy_name:'R1_ops',priv_lvl:15,command_sets:['Read_Only']}],by_privilege:{15:1},total_reachable:1,total_devices_checked:2},
 '/api/config/candidate':{applicable:true,has_changes:false,diff:'',candidate:'fixture',active:'fixture',diagnostics:[],uncompilable_policies:[]},
 };
}
module.exports={fixtures};
