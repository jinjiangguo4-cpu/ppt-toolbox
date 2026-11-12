const fs = require('node:fs');
const path = require('node:path');
const Pptx = require('pptxgenjs');
const root = process.argv[2];
const folder = '高级页面组件';
fs.mkdirSync(path.join(root,folder),{recursive:true});
const ink='152839', muted='426075', teal='006C64', pale='E9F4F1', amber='A24720', white='FFFFFF';
const templates=[
 ['release-gate','上线放行决策页','软件交付','上线会议逐项核对必须满足的条件与回滚触发线。',({t,b})=>{
   b(.8,2.05,7.6,3.85,pale);
   [['数据迁移','抽样核对 100 条记录'],['故障演练','已完成回滚与恢复演练'],['业务签收','运营与客服确认值班名单']].forEach(([a,c],i)=>{
      t(a,1.15,2.42+i,2, .5,19,teal);t(c,3.3,2.42+i,4.5,.5,18);
   });
   b(8.65,2.05,3.85,3.85,ink);
   t('放行决定',9,2.45,3.1,.5,22,white); t('有条件上线',9,3.15,3.1,.65,27,white);
   t('回滚触发：错误率连续 5 分钟超过 2%',9,4.24,3.05,1.05,17,white);
 }],
 ['procurement-tradeoff','采购方案取舍页','采购管理','把供应商优势与不可接受条件并列，再给出有前提的推荐。',({t,b})=>{
   [['方案 A','交付快','需预付 50%','适合紧急补货'],['方案 B','账期 60 天','最小订货量较高','适合稳定批次']].forEach(([a,c,d,e],i)=>{
      let x=.8+i*5.95;b(x,2,5.75,2.88,i?'F4EEE8':pale);
      t(a,x+.25,2.22,5.1,.48,23);t(c,x+.25,2.9,5.1,.4,19,teal);
      t(d,x+.25,3.45,5.1,.4,18,amber);t(e,x+.25,4.02,5.1,.4,17,muted);
   });
   b(.8,5.15,11.7,1.0,ink);t('推荐 B：仅在季度需求超过最小订货量时签约。',1.12,5.38,11,.5,21,white);
 }],
 ['coverage-handoff','交接闭环卡','运营管理','把上一班未决事项移交给下一班，明确验收时间和升级联系人。',({t,b})=>{
   b(.8,2,11.7,1.18,ink);t('未决事项   冷库 B 温度告警，已隔离对应批次',1.13,2.3,11,.54,23,white);
   [['交班证据','最近温度记录与受影响批次'],['接班动作','复测两个测点，更新隔离状态'],['闭环条件','18:00 前恢复正常并通知质检']].forEach(([a,c],i)=>{
      let x=.8+i*3.93;b(x,3.47,3.76,2.45,pale);t(a,x+.21,3.75,3.25,.48,22,teal);t(c,x+.21,4.43,3.25,.92,18);
   });
 }],
 ['experiment-stop-rule','试验停止规则页','产品实验','预先写清成功、继续和止损条件，避免在观察结果后修改规则。',({t,b})=>{
   [['提前停止','支付失败率上升 1 个百分点','立即关闭试验并复盘',amber],['继续观察','样本数不足 4,000','保持分流比例',muted],['进入推广','完成率提高且无护栏恶化','安排分阶段上线',teal]].forEach(([a,c,d,color],i)=>{
     let y=2.06+i*1.27;b(.8,y,2.6,1.05,color);t(a,1.03,y+.19,2.1,.61,21,white);b(3.55,y,8.95,1.05,'EDF2F6');t(c,3.82,y+.13,8.2,.37,18);t(d,3.82,y+.57,8.2,.33,15,muted);
   });
 }],
 ['policy-exception','政策例外申请页','治理合规','用一页记录常规限制、例外范围、补偿措施与到期复核。',({t,b})=>{
   b(.8,2,4.1,4.05,ink);t('常规限制',1.13,2.35,3.4,.5,22,white);t('外部协作者仅可访问脱敏测试环境。',1.13,3.08,3.4,1.5,25,white);
   [['例外范围','只读访问一套隔离演示库'],['补偿措施','限制账号、时段和数据导出'],['到期复核','周五自动撤权，由责任人确认']].forEach(([a,c],i)=>{
     let y=2+i*1.38;b(5.2,y,7.3,1.22,pale);t(a,5.45,y+.17,2,.45,19,teal);t(c,7.45,y+.17,4.75,.78,18);
   });
 }],
 ['learning-misconception','概念误区讲解页','教育培训','课堂先展示常见误解，再用对照情景和检查题验证理解。',({t,b})=>{
   b(.8,2,11.7,1.08,'F4EEE8');t('常见误区：平均数一定代表多数人的水平。',1.05,2.24,11,.52,22,amber);
   b(.8,3.32,7.35,2.78,pale);t('用反例拆解',1.08,3.57,6.7,.5,21,teal);
   t('五个人中四人的通勤时间为 20 分钟，一人为 120 分钟。平均为 40 分钟，中位数为 20 分钟。',1.08,4.27,6.7,1.3,19);
   b(8.39,3.32,4.11,2.78,ink);t('检查题',8.67,3.57,3.5,.5,22,white);t('哪项统计量更能描述典型通勤？说明理由。',8.67,4.34,3.47,1.18,19,white);
 }]
];
(async()=>{
 const rows=[];
 for(const [id,title,industry,usage,draw] of templates){
   const p=new Pptx();p.layout='LAYOUT_WIDE';p.title=title;p.author='PPT Toolbox';
   p.theme={headFontFace:'Arial Unicode MS',bodyFontFace:'Arial Unicode MS',lang:'zh-CN'};
   const s=p.addSlide();s.background={color:'FAFCFD'};
   const t=(value,x,y,w,h,fontSize,color=ink)=>s.addText(value,{x,y,w,h,fontSize,color,fontFace:'Arial Unicode MS',margin:0,isTextBox:true,valign:'mid',fit:'shrink'});
   const b=(x,y,w,h,color)=>s.addShape(p.ShapeType.rect,{x,y,w,h,fill:{color},line:{transparency:100}});
   b(.8,.64,.10,.64,teal);t(title,1.02,.58,11.4,.76,33);t(usage,1.02,1.32,11.4,.40,16,muted);
   b(.8,6.61,11.7,.013,'C5D8DE');t(industry+'  /  示例内容可替换',.8,6.78,11.7,.27,12,muted);
   draw({t,b});
   s.addNotes(usage+' 示例内容请替换为实际项目数据。');
   const rel=folder+'/'+id+'.pptx';
   await p.writeFile({fileName:path.join(root,rel)});
   rows.push({id:'pptb005-'+id,name_zh:title,name_en:id.replaceAll('-',' '),category:'高级页面组件',subcategory:industry,keywords_zh:[title,industry],industries:[industry],motif_key:id,file_path:rel,editability:'native-shapes-and-text',powerpoint_app_verification:'未完成 PowerPoint 实测'});
 }
 fs.writeFileSync(path.join(root,'资源描述.json'),JSON.stringify(rows,null,2)+'\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
