"""Generate distinct original backgrounds and transparent accents with fixed geometry."""
from html import escape
import json
from math import sin, cos, tau
from pathlib import Path
from random import Random
import sys
from xml.etree import ElementTree

out = Path(sys.argv[1])
W,H = 960,540


def path(d, stroke, width=1, fill="none"):
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'


def rect(x,y,w,h,fill,r=0):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"/>'


def dot(x,y,r,fill):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/>'


def points(coords, stroke, width=1, fill="none", closed=False):
    d = "M"+" L".join(f"{x:.1f} {y:.1f}" for x,y in coords)+(" Z" if closed else "")
    return path(d,stroke,width,fill)


def loop(x,y,r,n=6,phase=0):
    return [(x+r*cos(tau*i/n+phase),y+r*sin(tau*i/n+phase)) for i in range(n)]


def noise(seed, count, color):
    g=Random(seed)
    return '<g opacity=".43">'+''.join(dot(g.randrange(W),g.randrange(H),g.choice((.45,.7,1)),color) for _ in range(count))+'</g>'


navy="#18354e"; blue="#23648b"; soft="#d6e8f4"; teal="#227b74"; rust="#b55a38"
items=[]
def save(slug,name,kind,usage,body,bg=None,view=(960,540)):
    w,h=view
    folder=out/kind; folder.mkdir(parents=True,exist_ok=True)
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
         f'<title>{escape(name)}</title><desc>{escape(usage)}</desc>'
         +(rect(0,0,w,h,bg) if bg else "")+body+'</svg>\n')
    ElementTree.fromstring(svg)
    (folder/(slug+".svg")).write_text(svg)
    items.append(dict(id="pptb004-"+slug,name_zh=name,name_en=slug.replace("-"," "),category=kind,
                      subcategory="原创矢量",keywords_zh=[name,usage],industries=["all"],motif_key=slug,
                      file_path=f"{kind}/{slug}.svg",editability="SVG-path-editable"))


def bg(slug, name, usage, body, color="#f6fafc"):
    save(slug,name,"材质背景",usage,body,color)


bg("survey-contour-rim","右侧地形等高线背景","户外、区域规划封面，左侧留白",
   ''.join(points([(780+(r*(1+.16*sin(3*a)))*cos(a),248+(r*(1+.13*cos(5*a)))*sin(a))
        for i in range(90) for a in [tau*i/90]],"#a9c9bd",1.35,closed=True) for r in range(40,360,22)),"#f0f7f4")
bg("technical-coordinate-field","技术坐标纸背景","工程研究、技术路线图，局部定位",
   ''.join(path(f"M{x} 0V540","#d5e5ef",1) for x in range(0,960,24))+
   ''.join(path(f"M0 {y}H960","#d5e5ef",1) for y in range(0,540,24))+
   path("M192 0V540 M0 384H960","#a7c7d9",2))
bg("linen-fibers","横纵亚麻纤维背景","文化与生活方式，浅色文字区",
   ''.join(path(f"M0 {y}H960",("#e8dece","#e1d5c2")[y%2],.6) for y in range(1,540,3))+
   ''.join(path(f"M{x} 0V540","#e7dccb",.45) for x in range(1,960,4))+noise(22,750,"#c9b79c"),"#f7f1e7")
bg("glass-prism-edge","玻璃折射侧边背景","科研或产品页，右缘轻质光学层",
   ''.join(points(v,"none",0,c,True) for v,c in [
     ([(548,540),(790,0),(950,0),(702,540)],"#e1f0f8"),
     ([(676,540),(835,0),(960,0),(960,540)],"#cee5f3"),
     ([(760,540),(960,90),(960,540)],"#b4d5e9")]))
bg("brushed-alloy","拉丝合金背景","制造设备细节页，配深色正文",
   ''.join(path(f"M{(i*139)%670} {y}h{80+(i*79)%460}", "#c2cdd4" if i%3 else "#d0d9df",.65)
     for i,y in enumerate(range(1,540,2))),"#e8edf0")
bg("ink-grain-paper","柔和墨点纸张背景","编辑型图文与历史叙事",
   noise(61,2600,"#c6b28c")+path("M0 532H960","#dfceb3",16),"#fbf6ed")
bg("riverbank-flow","河岸流线背景","生态或地理叙事，顶部留白",
   ''.join(path(f"M-20 {398+i*12} C210 {470+i*11} 512 {348+i*13} 980 {411+i*13}","#91bdb8",2) for i in range(11)),"#eff8f7")
bg("soft-horizon","柔光地平线背景","开场或章节切换，顶部深底",
   '<defs><linearGradient id="g" x2="0%" y2="100%"><stop stop-color="#122641"/><stop offset=".64" stop-color="#2f536e"/><stop offset="1" stop-color="#966d77"/></linearGradient></defs>'+
   rect(0,0,960,540,"url(#g)")+path("M0 418C197 386 410 434 610 409S854 384 960 420L960 540H0Z","none",0,"#172d49"))
bg("ceramic-tile-corner","手工瓷砖边角背景","手作、空间展示，侧边局部纹样",
   ''.join(rect(x,y,35,35,["#b6d6d1","#cae2df","#ddebe7"][(x+y)//38%3],3)
      for x in range(730,965,38) for y in range(8,540,38) if x+2*y>1040),"#f7fbf9")
bg("wave-interference","波纹干涉背景","声学或信号图解，图案靠右",
   '<g fill="none" stroke="#c4dbef" stroke-width="1.1">'+''.join(f'<circle cx="{x}" cy="302" r="{r}"/>'
      for x in (780,915) for r in range(24,345,17))+"</g>","#f1f7fb")
bg("book-margin","书页折边背景","报告正文、课程讲义，左侧定位线",
   rect(0,0,111,540,"#ede7db")+rect(109,0,3,540,"#caa779")+path("M0 511H960","#e4d9c7"),"#faf7f1")
bg("layered-bedrock","岩层剖面背景","能源、岩土和城市建设封面",
   ''.join(path(d,"none",0,c) for d,c in [
      ("M0 415Q260 361 510 409T960 371V540H0Z","#dbcabb"),
      ("M0 462Q280 422 548 452T960 418V540H0Z","#bfa79a"),
      ("M0 505Q265 467 550 492T960 459V540H0Z","#9d837a")]),"#f7f1ec")

def accent(slug,name,usage,body):
    save(slug,name,"特殊装饰",usage,body,view=(400,220))


accent("instrument-ruler-edge","仪表刻度侧签","为工程数据旁边提供视觉定位",
       path("M25 179H380",navy,3)+''.join(path(f"M{x} 179v{-26 if i%5==0 else -12}",blue,2)
          for i,x in enumerate(range(25,381,10))))
accent("focus-brackets","四角取景括线","标注图片中的关键区域",
       path("M35 78V37H92 M308 37H365V78 M365 142V183H308 M92 183H35V142",teal,7))
accent("section-break-bars","节间强弱线","用于两个内容组之间的短分隔",
       rect(23,103,154,8,navy)+rect(185,105,69,4,teal)+rect(262,106,114,2,"#a5c3cc"))
accent("annotation-elbow-dot","折角注释引线","连接图片细节和旁注",
       path("M51 159H175L251 78H369",blue,4)+dot(51,159,10,blue)+dot(369,78,6,teal))
accent("woven-knot-mark","编织交错角饰","文化主题图片的边角装饰",
       path("M64 157L150 70L237 157L323 70 M64 70L150 157L237 70L323 157",rust,13)+
       path("M132 139L168 103 M218 103L254 139","#f1c4aa",7))
accent("dotted-travel-arc","点状航迹弧线","用于表达跨地域连接和移动",
       '<path d="M30 162Q174 14 348 104" fill="none" stroke="#23648b" stroke-width="4" stroke-dasharray="3 12"/>'+
       points([(342,88),(374,112),(334,115)],"none",0,blue,True))
accent("stacked-isometric-layers","等距分层示意装饰","提示架构或材料分层",
       ''.join(points([(49,y),(202,y-39),(350,y),(202,y+39)],navy,2,c,True)
          for y,c in [(154,"#d7e8ed"),(121,"#98c7cf"),(87,"#4d97a6")]))
accent("editorial-fold-tab","折页页角标签","用于案例、附录或专题角标",
       points([(194,21),(381,21),(381,151),(322,151),(291,188),(291,151),(194,151)],"none",0,navy,True)+
       points([(291,151),(322,151),(291,188)],"none",0,teal,True))
accent("cluster-orbit-mark","轨道聚合装饰","用于系统、协作和平台视觉",
       '<ellipse cx="200" cy="110" rx="151" ry="63" fill="none" stroke="#23648b" stroke-width="3" transform="rotate(-16 200 110)"/>'+
       dot(200,110,23,navy)+dot(85,98,11,teal)+dot(324,130,14,rust))
accent("split-proportion-brace","比例拆分括线","横向图表上方标记两个区间",
       path("M35 153V96H158L200 64L242 96H365V153 M200 64V35",teal,5))
accent("data-node-fork","分叉节点装饰","提示内容进入不同分支",
       path("M51 109H166 M166 109L268 52H344 M166 109L268 164H344",blue,4)+
       ''.join(dot(x,y,9,teal) for x,y in [(51,109),(166,109),(344,52),(344,164)]))
accent("scale-chevron-chain","层叠方向箭头","用于跨页导航或过渡",
       ''.join(points([(x,45),(x+78,110),(x,175),(x+33,175),(x+111,110),(x+33,45)],"none",0,c,True)
          for x,c in [(31,"#b9d5e7"),(109,"#639fbf"),(187,blue)]))
accent("six-cell-molecule","六边形网格角饰","用于实验、医疗或工程专题",
       ''.join(points(loop(x,y,28,6,tau/12),teal,3,"#d8eeec" if i==3 else "none",True)
          for i,(x,y) in enumerate([(130,64),(178,64),(226,64),(154,106),(202,106),(250,106),(178,148)])))

assert len(items)==25
(out/"资源描述.json").write_text(json.dumps(items,ensure_ascii=False,indent=2)+"\n")
