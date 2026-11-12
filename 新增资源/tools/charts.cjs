const fs = require('node:fs');
const path = require('node:path');
const PptxGen = require('pptxgenjs');
const output = process.argv[2];
const chartPath = path.join(output, '图表与信息图');
fs.mkdirSync(chartPath, {recursive:true});

const definitions = [
 ['variance-plan','计划与实际差额','column','千元','经营管理','按月份并列两组柱形，检查预算差距','一月 二月 三月 四月',[['计划',55,60,65,70],['实际',51,64,62,76]]],
 ['backlog-age','积压工单账龄','bar','件','客户服务','用横条突出长账龄工单规模','0–7天 8–14天 15–30天 30天以上',[['工单',42,27,17,11]]],
 ['cost-mix','成本结构占比','percent','%','经营管理','以同一基准比较各厂成本结构','甲厂 乙厂 丙厂',[['人工',46,38,42],['材料',33,40,38],['其他',21,22,20]]],
 ['stock-flow','安全库存与现货','line','件','供应链','把安全库存作为独立基准线','周一 周二 周三 周四 周五 周六',[['现货',132,119,87,76,93,115],['安全库存',90,90,90,90,90,90]]],
 ['cash-buffer','现金缓冲区间','area','万元','经营管理','显示期内现金覆盖与压力情景','一月 二月 三月 四月 五月 六月',[['压力情景',20,22,17,21,19,29],['与基准差额',13,18,21,28,28,26]]],
 ['demand-by-channel','渠道增量拆分','stack','单','零售','对比各月总量，并显示渠道贡献','一月 二月 三月 四月',[['直营网店',23,25,26,35],['门店',15,14,20,21],['经销',10,12,11,14]]],
 ['channel-single','单期渠道构成','doughnut','%','市场营销','同一时段四种获客渠道构成','自然搜索 推荐 合作 活动',[['获客',42,28,19,11]]],
 ['queue-spread','响应时长分布','hist','单','客户服务','显示按等宽区间分组后的响应时长','0–15 15–30 30–45 45–60 60–75 75–90',[['工单',7,19,35,24,13,5]]],
 ['target-gap','目标缺口正负分布','bar','百分点','经营管理','观察不同项目偏离目标的方向与幅度','门店A 门店B 门店C 门店D 门店E',[['目标差',5,-3,2,-7,4]]],
 ['completion-funnel','报名到参与转化漏斗','funnel','人','教育','各环节按初始人数缩放，同时显示人数','浏览 报名 确认 到场',[['参与人数',150,96,72,57]]],
 ['supply-heatmap','仓库时段负载热力图','heat','%','供应链','按仓库与班次定位超负载时段','早班 午班 晚班 夜班',[['仓库A',49,67,84,31],['仓库B',58,83,91,52],['仓库C',66,55,71,45]]],
 ['training-ladder','岗位培训掌握度阶梯','ladder','等级','教育','将技能门槛与考核方式并列','认知 练习 独立作业 带教',[['学习等级',1,2,3,4]]],
 ['defect-pareto','质量缺陷帕累托拆解','pareto','件','制造','按次数排序，并列累计占比','划伤 偏差 松动 污染 其他',[['缺陷',37,22,12,7,2]]],
 ['incident-timeline','故障响应事件轴','timeline','分钟','技术','定位发现、止损、恢复与复盘的间隔','发现 升级 止损 恢复 复盘',[['时间',0,12,29,52,86]]],
 ['confidence-interval','采样误差区间图','range','%','用户研究','同时显示点估计与上下界','方案A 方案B 方案C',[['下界',43,51,49],['估计',52,61,57],['上界',61,71,65]]],
 ['base-bridge','利润变动桥接图','bridge','万元','财务','从期初到期末，显示正负驱动因素','期初 价格 成本 损耗 期末',[['变动',50,15,-8,-5,52]]],
 ['priority-grid','影响与投入优先级','quadrant','评分','产品设计','同时定位影响与实施投入','引导页 搜索 排序 通知',[['投入',2,7,4,6],['影响',8,9,4,3]]],
 ['risk-map','风险概率与影响矩阵','quadrant','评分','风险管理','用编号定位风险，并以横纵轴表达严重度','延期 断供 退货 停机',[['概率',7,3,5,8],['影响',3,9,5,9]]],
 ['water-balance','供水量与损耗核对','stack','千立方米','公共服务','并列供水去向，显示计量与未计量部分','北区 东区 南区',[['有效供水',61,52,58],['计量损耗',12,16,9],['未计量',8,11,7]]],
 ['seasonal-profile','环比与去年同期走势','line','指数','零售','以相同时间轴比较季节波动','三月 四月 五月 六月 七月 八月',[['本年',92,96,110,113,104,100],['上年同期',85,91,101,108,98,94]]],
 ['utilization-bullet','产能利用率目标带','bullet','%','制造','用背景区间和目标标记表示达标情况','产线A 产线B 产线C',[['实际',68,84,77],['目标',75,80,85]]],
 ['reliability-radar','系统可靠性维度雷达','radar','分','技术','多维指标统一到百分制后比较','可用性 备份 恢复 告警 隔离 演练',[['当前',82,76,64,79,68,70],['目标',90,85,85,85,85,80]]],
 ['product-score','产品试用评价分布','percent','%','用户研究','按产品展示正面、中立和负面评价占比','方案A 方案B 方案C',[['正面',52,64,42],['中立',31,24,38],['负面',17,12,20]]],
 ['inventory-treemap','库存占用面积图','treemap','万元','供应链','用面积编码不同商品类的占用规模','机械件 电气件 包材 耗材',[['库存',42,26,19,13]]],
 ['cycle-lanes','交付周期分段条','stack','天','项目管理','将各工作流的处理与等待时长拆开','评审 开发 验收 交付',[['处理',2,6,3,2],['等待',4,1,2,5]]],
];
const C={ink:'172B42',muted:'4C6174',light:'E6EEF4',blue:'1768A8',teal:'12796C',rust:'B55137',line:'CDD9E4',white:'FFFFFF'};
const palette=[C.blue,C.teal,C.rust,'624B92'];
const sw=13.333,sh=7.5;
function text(s,value,x,y,w,h,opts={}){
 s.addText(String(value),{x,y,w,h,margin:0,fontFace:'Arial Unicode MS',fontSize:15,color:C.ink,breakLine:false,isTextBox:true,fit:'shrink',...opts});
}
function box(p,s,x,y,w,h,fill){
 s.addShape(p.ShapeType.rect,{x,y,w,h,line:{transparency:100},fill:{color:fill}});
}
function segment(p,s,x1,y1,x2,y2,color=C.line,width=1){
 s.addShape(p.ShapeType.line,{x:Math.min(x1,x2),y:Math.min(y1,y2),w:Math.abs(x2-x1),h:Math.abs(y2-y1),flipV:(x2-x1)*(y2-y1)<0,line:{color,width}});
}
function circle(p,s,x,y,r,fill){
 s.addShape(p.ShapeType.ellipse,{x:x-r,y:y-r,w:r*2,h:r*2,line:{transparency:100},fill:{color:fill}});
}
function diagram(p,s,kind,labels,series){
 const vals=series[0].values;
 if(kind==='funnel'||kind==='ladder'){
  labels.forEach((v,i)=>{
   const y=2.05+i*.95,w=7*(kind==='funnel'?vals[i]/vals[0]:vals[i]/4),x=kind==='funnel'?6.9-w/2:3.4;
   box(p,s,x,y,w,.66,palette[i]);text(s,v,.85,y,2.55,.66);
   text(s,kind==='ladder'?'L'+vals[i]:vals[i],x+.06,y,w-.12,.66,{color:C.white,bold:true,align:'center'});
  });
 }else if(kind==='heat'){
  labels.forEach((v,j)=>text(s,v,3.15+j*2.1,2.00,1.75,.3,{align:'center'}));
  series.forEach((r,i)=>{
   text(s,r.name,.84,2.55+i*.94,2,.58);
   r.values.forEach((n,j)=>{
    const fill=n>=80?C.rust:n>=60?C.blue:C.light;
    box(p,s,3.15+j*2.1,2.55+i*.94,1.75,.64,fill);text(s,n+'%',3.15+j*2.1,2.55+i*.94,1.75,.64,{align:'center',bold:true,color:n>=60?C.white:C.ink});
   });
  });
 }else if(kind==='timeline'){
  segment(p,s,1.05,3.63,12.10,3.63,C.line,3);
  vals.forEach((v,i)=>{
   const x=1.15+10.75*v/vals.at(-1);
   circle(p,s,x,3.63,.12,i===vals.length-1?C.teal:C.blue);
   text(s,labels[i],x-.55,2.94,1.1,.4,{align:'center',bold:true});
   text(s,v+' 分',x-.55,4.08,1.1,.4,{align:'center'});
  });
 }else if(kind==='range'||kind==='bullet'||kind==='pareto'){
  const n=labels.length;
  labels.forEach((v,i)=>{
   const y=2.2+i*(3.75/n);
   text(s,v,.85,y-.04,2.1,.42);
   box(p,s,3.2,y,7.2,.35,C.light);
   if(kind==='range'){
    const lo=vals[i],mid=series[1].values[i],hi=series[2].values[i];
    segment(p,s,3.2+lo*.072,y+.175,3.2+hi*.072,y+.175,C.teal,4);
    circle(p,s,3.2+mid*.072,y+.175,.105,C.blue);text(s,lo+'–'+hi+'%',10.65,y-.04,1.65,.42);
   } else if(kind==='bullet'){
    box(p,s,3.2,y+.04,vals[i]*.072,.27,C.blue);
    const goal=3.2+series[1].values[i]*.072;
    segment(p,s,goal,y-.07,goal,y+.42,C.rust,3);text(s,vals[i]+'%',10.65,y-.04,1.65,.42);
   } else {
    box(p,s,3.2,y,7.2*vals[i]/vals[0],.35,C.blue);
    const total=vals.reduce((a,b)=>a+b,0);
    const acc=vals.slice(0,i+1).reduce((a,b)=>a+b,0);
    text(s,vals[i]+' 件 · '+Math.round(100*acc/total)+'%',10.55,y-.04,2.03,.42);
   }
  });
 }else if(kind==='quadrant'){
  const x=2.0,y=2.0,w=9.25,h=3.64;
  box(p,s,x,y,w,h,C.light);segment(p,s,x+w/2,y,x+w/2,y+h,C.white,2);
  segment(p,s,x,y+h/2,x+w,y+h/2,C.white,2);
  labels.forEach((v,i)=>{
   const px=x+w*vals[i]/10,py=y+h*(1-series[1].values[i]/10);
   circle(p,s,px,py,.12,palette[i]);text(s,v,px+.16,py-.21,1.1,.42,{bold:true,fontSize:13});
  });
  text(s,series[0].name+' →',9.8,5.82,1.5,.35);
  text(s,series[1].name+' ↑',.65,2,1.2,.35);
 }else if(kind==='bridge'){
  let value=0;
  const baseline=5.75,scale=.048;
  labels.forEach((v,i)=>{
   const terminal=i===0||i===labels.length-1;
   const old=terminal?0:value;value=terminal?vals[i]:value+vals[i];
   const x=1.15+i*2.27,top=Math.max(old,value);
   box(p,s,x,baseline-top*scale,1.44,Math.abs(value-old)*scale,terminal?C.blue:vals[i]>0?C.teal:C.rust);
   text(s,(terminal||vals[i]<0?'':'+')+vals[i],x,baseline-top*scale-.4,1.44,.32,{align:'center',bold:true});
   text(s,v,x,baseline+.15,1.44,.32,{align:'center'});
  });
 }else if(kind==='treemap'){
  const total=vals.reduce((a,b)=>a+b,0);let x=.85;
  labels.forEach((v,i)=>{
   const w=11.65*vals[i]/total;
   box(p,s,x,2.1,w-.05,3.55,palette[i]);
   text(s,v,x+.1,3.0,w-.22,.45,{color:C.white,bold:true,align:'center'});
   text(s,vals[i]+' 万',x+.1,3.66,w-.22,.45,{color:C.white,align:'center'});x+=w;
  });
 }
}
async function main(){
 const items=[];
 for(const [id,title,kind,unit,industry,usage,labelsString,raw] of definitions){
  const p=new PptxGen();p.layout='LAYOUT_WIDE';p.author='PPT Toolbox';p.title=title;
  p.theme={headFontFace:'Arial Unicode MS',bodyFontFace:'Arial Unicode MS',lang:'zh-CN'};
  p.defineSlideMaster({title:'Analysis',background:{color:C.white},objects:[]});
  const s=p.addSlide({masterName:'Analysis'});
  box(p,s,.64,.56,.09,.62,C.teal);
  text(s,title,.88,.5,11.8,.67,{fontSize:33,bold:true});
  text(s,usage,.88,1.30,11.6,.4,{fontSize:16,color:C.muted});
  segment(p,s,.82,6.64,12.49,6.64,C.line);
  text(s,'演示数据  /  '+unit,.87,6.78,11.5,.3,{fontSize:11,color:C.muted});
  const labels=labelsString.split(' ');
  const series=raw.map(([name,...values])=>({name,labels,values}));
  const chartKinds={column:p.ChartType.bar,bar:p.ChartType.bar,stack:p.ChartType.bar,percent:p.ChartType.bar,hist:p.ChartType.bar,line:p.ChartType.line,area:p.ChartType.area,radar:p.ChartType.radar,doughnut:p.ChartType.doughnut};
  if(chartKinds[kind]){
   const opt={x:.85,y:1.94,w:11.57,h:4.55,chartColors:palette,showLegend:series.length>1||kind==='doughnut',legendPos:'b',legendFontSize:11,catAxisLabelFontSize:11,valAxisLabelFontSize:10,valGridLine:{color:C.light,size:1},catGridLine:{style:'none'},showValue:kind==='doughnut',showPercent:kind==='doughnut',dataLabelPosition:'bestFit',showTitle:false,showMarker:kind==='line',lineSize:3};
   if(['bar','column','stack','percent','hist'].includes(kind)){
    opt.barDir=kind==='bar'?'bar':'col';opt.gapWidthPct=kind==='hist'?8:65;
    if(kind==='stack'||kind==='percent')opt.barGrouping=kind==='stack'?'stacked':'percentStacked';
   }
   if(kind==='percent'){opt.valAxisMinVal=0;opt.valAxisMaxVal=1;opt.valAxisNumFmt='0%';}
   if(kind==='area')opt.catAxisLabelFontFace='Arial Unicode MS',opt.barGrouping='stacked';
   opt.legendFontFace='Arial Unicode MS';opt.catAxisLabelFontFace='Arial Unicode MS';
   if(kind==='radar'){opt.valAxisMinVal=0;opt.valAxisMaxVal=100;}
   if(kind!=='doughnut')delete opt.dataLabelPosition;
   s.addChart(chartKinds[kind],series,opt);
  }else diagram(p,s,kind,labels,series);
  s.addNotes('用法：'+usage+'。本页所有数据为演示数据。'+(chartKinds[kind]?'可通过编辑数据更改图表。':'图形和文字可逐项编辑，改数值后请同步调整几何尺寸。'));
  const filePath='图表与信息图/'+id+'.pptx';
  await p.writeFile({fileName:path.join(output,filePath)});
  items.push({id:'pptb002-'+id,name_zh:title,name_en:id.replaceAll('-',' '),category:'图表与信息图',subcategory:kind,keywords_zh:[industry,title],industries:[industry],motif_key:id,file_path:filePath,editability:chartKinds[kind]?'native-chart-with-workbook':'native-shapes-and-text',chart:!!chartKinds[kind]});
 }
 fs.writeFileSync(path.join(output,'资源描述.json'),JSON.stringify(items,null,2)+'\n');
}
main().catch(error=>{console.error(error);process.exitCode=1});
