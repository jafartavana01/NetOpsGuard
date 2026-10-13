/* Synthetic API fixtures; never used by application code. */
const stamp='2026-10-13T08:00:00Z';
function fixtures(){return {
 '/api/admin-users':[{id:'a1',username:'owner',is_active:true,is_superadmin:true,role_id:null,role_name:null,allowed_source_ips:null,last_login_at:stamp,is_self:true},{id:'a2',username:'reader',is_active:true,is_superadmin:false,role_id:'r1',role_name:'Read only',allowed_source_ips:'192.0.2.0/24',last_login_at:null,is_self:false}],
 '/api/admin-roles':[{id:'r1',name:'Read only',description:'Operations visibility',permissions:['devices:view'],is_template:true,admin_count:1}],
 '/api/admin-roles/permission-catalog':[{key:'devices:view',label:'View devices',description:'Read device inventory'},{key:'devices:write',label:'Manage devices',description:'Change device inventory'},{key:'config:apply',label:'Apply configuration',description:'Apply a valid candidate'}],
 '/api/platform-settings':{web_host:'0.0.0.0',web_port:8443,https_enabled:true,tacacs_port:49,certificate:{common_name:'netops.example.test',organization:'Test organization',is_expired:false,not_valid_before:stamp,not_valid_after:'2027-10-13T08:00:00Z',serial_number:'12345'}},
 '/api/platform-settings/restart-management-service':{status:'restarting'},
 '/api/ad-settings':{enabled:true,host:'ad.example.test',port:636,use_tls:true,use_starttls:false,bind_dn:'CN=service,OU=Accounts,DC=example,DC=test',has_password:true,search_base:'DC=example,DC=test',user_filter_template:'(&(objectClass=user)(sAMAccountName=%s))',group_prefix:'AAA_',use_memberof:true,updated_at:stamp},
 '/api/ad-settings/test':{success:true,message:'LDAP bind succeeded.',detail:{}},
 '/api/ad-settings/health':{success:true,message:'Saved LDAP connection succeeded.',detail:{}},
 '/api/modules':[{key:'core',name:'Core',description:'Required platform management',enabled:true,mandatory:true,nav_paths:['/platform/settings'],route_count:20},{key:'ncm',name:'Configuration Management',description:'Device backups and changes',enabled:true,mandatory:false,nav_paths:['/ncm/dashboard'],route_count:14}],
 '/api/license':{edition_key:'community',edition_name:'Community',edition_description:'Free for up to five devices.',licensed:false,customer:null,license_id:null,fingerprint:'abcd',expires_at:null,days_remaining:null,development_key:false,problem:'',machine_short_id:'test-machine',machine_bound:false,device_limit:5,device_count:3,admin_limit:1,admin_count:1,grandfathered_device_count:0,at_device_limit:false,device_limit_message:'',features:[{key:'aaa',name:'AAA',description:'Authentication and authorization',included:true}],editions_available:[{name:'Community',description:'Free edition',device_limit:5,admin_limit:1,features:['aaa'],current:true}]},
 '/api/system/status':{checked_at:stamp,os:'Synthetic Linux',database:'connected',services:{'aaa-platform.service':{active_state:'active',sub_state:'running',enabled:true},'tac-plus-ng.service':{active_state:'failed',sub_state:'failed',enabled:true}},build_info:{status:'recorded',build_profile:'openssl',build_date_utc:stamp,features_detected_enabled:['TLS']}},
 '/api/diagnostics/overview':{services:{'aaa-platform.service':{active_state:'active'},'tac-plus-ng.service':{active_state:'unknown'}},build_info:{}},
 '/api/diagnostics/validate-config':{applicable:false,would_change:false,validated:false,definitively_failed:true,output:'Policy scope invalid.',diagnostics:[{protocol:'tacacs',policy_name:'R1',reason:'The referenced group is empty.',code:'scope.empty_group',path:'legacy.group',object_id:'g1'}]},
 '/api/diagnostics/audit-events':{events:[{id:1,event_type:'config_apply_failed',detail:'password=do-not-display <img src=x onerror="window.injected=1">',occurred_at:stamp}]},
 '/api/diagnostics/service-log/aaa-platform.service':{content:'service active\npassword=do-not-display\nsecret="do-not-display"\npostgresql://admin:do-not-display@localhost/db'},
 '/api/diagnostics/service-log/tac-plus-ng.service':{content:'tacacs failed\nradius.key = "do-not-display"'},
 '/api/tacacs-logs/access':{content:'access record for operator'},
 '/api/tacacs-logs/authorization':{content:'authorization denied'},
 '/api/tacacs-accounting/health':{total_records_in_tail:10,parsed_records:9,unparsed_records:1,events_last_hour:2,distinct_devices:3,distinct_users:2,permit_count:4,non_permit_count:1,by_accttype:{start:4,stop:5},top_non_permit_devices:[{name:'R1',count:1}],top_non_permit_users:[{name:'reader',count:1}],result_counts:{permit:4,deny:1}},
 '/api/radius/settings':{enabled:true,auth_port:1812,acct_port:1813,include_dictionaries:true,protocol:'UDP',devices_with_radius:1},
 '/api/radius/listeners':[{port:1812,listening:true,loopback_only:false,detail:'UDP listener found',guidance:''},{port:1813,listening:false,loopback_only:false,detail:'No UDP listener found',guidance:'Review and apply saved settings'}],
 '/api/radius/clients':[{device_id:'d1',device_name:'R1',ip_address:'192.0.2.1',has_secret:true}],
 '/api/radius/probe':{reachable:true,detail:'Access-Reject received',round_trip_ms:2,target:'127.0.0.1:1812',guidance:''}
};}
module.exports={fixtures};
