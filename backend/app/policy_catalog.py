"""Source-reviewed initial rule pack; retrieval coverage is not executable-rule coverage.

The catalog is a finite inventory of the supplied policies, not an LLM extraction result.
Each executable constraint below names a source article and is resolved against its real text.
"""

import json
import re
from copy import deepcopy
from pathlib import Path

SOURCE_REVIEW_MANIFEST = json.loads(
    (Path(__file__).parent / "research_data/source_review_manifest.json").read_text(
        encoding="utf-8"
    )
)["sources"]

# id, name, category, literal source terms. One provision may support several matters.
TOPICS = [
    (
        "resident_pension_enroll",
        "城乡居民养老保险参保",
        "养老保险",
        "参保范围|年满16|年满 １６|户籍地",
    ),
    (
        "resident_pension_pay",
        "城乡居民养老保险缴费、补缴及补助",
        "养老保险",
        "个人缴费|缴费补贴|代缴|补缴|缴费档次",
    ),
    (
        "resident_pension_benefit",
        "城乡居民养老待遇领取与资格核验",
        "养老保险",
        "城乡居民养老保险待遇|待遇领取条件|年满 ６０|基础养老金",
    ),
    (
        "resident_pension_transfer",
        "城乡居民养老保险转移衔接",
        "养老保险",
        "户籍迁移|迁入地|城乡居民基本养老保险且未享受待遇",
    ),
    ("pension_account", "养老个人账户查询、计息及继承", "养老保险", "个人账户|继承|指定受益人"),
    ("pension_funeral", "养老遗属丧葬补助及抚恤金", "养老保险", "死亡|丧葬|遗属|抚恤"),
    ("pension_disability", "病残津贴", "养老保险", "病残津贴|因病或者非因工致残"),
    (
        "employee_pension_enroll",
        "职工及灵活就业人员养老参保",
        "养老保险",
        "灵活就业|企业职工|职工应当参加",
    ),
    (
        "employee_pension_pay",
        "职工养老缴费与欠费补缴",
        "养老保险",
        "缴费工资|缴费基数|征缴|税务|按时足额",
    ),
    (
        "employee_pension_benefit",
        "职工基本养老金申领与计发",
        "养老保险",
        "基本养老金|过渡性养老金|领取基本养老",
    ),
    (
        "retirement",
        "渐进延迟、弹性及特殊工种退休",
        "养老保险",
        "退休年龄|提前退休|延迟退休|最低缴费年限|特殊工种",
    ),
    (
        "pension_transfer",
        "职工养老保险转移接续与转入",
        "养老保险",
        "转移|转入|接续|临时基本养老保险",
    ),
    (
        "pension_location",
        "跨省养老待遇领取地确定",
        "养老保险",
        "待遇领取地|上一个缴费|满10年|满１０年",
    ),
    ("enterprise_annuity", "企业年金", "养老保险", "企业年金"),
    (
        "employee_medical_enroll",
        "职工及灵活就业人员医保参保",
        "医疗保险",
        "职工医保登记|职工基本医疗保险|职工医保|灵活就业",
    ),
    (
        "resident_medical_enroll",
        "居民及学生医保参保",
        "医疗保险",
        "居民医保|居民基本医疗保险|大学生|学生",
    ),
    ("newborn_medical", "新生儿医保登记与待遇", "医疗保险", "新生儿|出生90日"),
    ("medical_pay", "医保缴费、补缴与等待期", "医疗保险", "缴费|等待期|次月起享受"),
    (
        "medical_subsidy",
        "困难人员医保参保资助",
        "医疗保险",
        "缴费补助|缴费资助|资助参保|分类资助|全额资助|个人缴费由",
    ),
    (
        "medical_retirement",
        "职工医保退休年限与补缴",
        "医疗保险",
        "法定退休|累计缴费年限|退休后不再缴纳",
    ),
    ("medical_account", "医保个人账户使用、共济与继承", "医疗保险", "个人账户|门诊和购药补助"),
    ("medical_outpatient", "普通门诊医保待遇", "医疗保险", "普通门诊|门诊共济|门诊起付"),
    ("medical_chronic", "门诊慢特病医保待遇", "医疗保险", "慢性|慢特病|重症|双通道"),
    ("medical_hospital", "住院医保待遇", "医疗保险", "住院|转院|医疗机构等级"),
    ("medical_reimbursement", "医疗费用直接结算与手工报销", "医疗保险", "结算|报销|垫付|收费票据"),
    (
        "medical_exclusion",
        "医保支付范围与先行支付",
        "医疗保险",
        "不予支付|不纳入|先行支付|药品目录|第三人",
    ),
    ("medical_abroad", "异地就医备案、转诊与结算", "医疗保险", "异地|统筹范围以外|非本市|转诊"),
    ("medical_transfer", "医保关系转移与制度衔接", "医疗保险", "关系转移|跨统筹地区|制度衔接"),
    ("serious_illness", "城乡居民大病保险赔付", "医疗保险", "大病保险|大病医疗保险"),
    ("aid_identification", "医疗救助对象认定", "医疗保险", "救助对象|因病致贫|身份认定"),
    (
        "aid_outpatient",
        "门诊慢特病医疗救助",
        "医疗保险",
        "门诊医疗救助|门诊慢特病医疗救助|自付门诊|自付合规门诊",
    ),
    ("aid_hospital", "住院医疗救助", "医疗保险", "住院医疗救助|住院救助|年度住院|自付合规部分"),
    ("aid_tilt", "倾斜救助与防返贫保障", "医疗保险", "倾斜救助|托底保障|预警|返贫"),
    (
        "aid_application",
        "医后救助与依申请救助",
        "医疗保险",
        "医后救助|依申请|医疗救助申请|治疗终结",
    ),
    (
        "aid_direct",
        "医疗救助即时结算与先诊疗后付费",
        "医疗保险",
        "即时结算救助|一站式|先诊疗|住院押金|免收",
    ),
    ("emergency_aid", "疾病应急救助与慈善帮扶", "医疗保险", "疾病应急救助|慈善|社会捐助|重大疫情"),
    (
        "medical_provider",
        "定点医药机构申请与协议管理",
        "医疗保险",
        "定点申请|协议管理|服务协议|承办资质|招投标|招标|准入条件",
    ),
    (
        "unemployment_enroll",
        "失业保险参保登记与缴费",
        "失业保险",
        "登记手续|缴纳失业保险费|缴费单位|缴费个人|缴费费率",
    ),
    (
        "unemployment_register",
        "失业登记及解除劳动关系证明",
        "失业保险",
        "失业登记|中断就业|解除劳动关系的证明",
    ),
    (
        "unemployment_benefit",
        "失业保险金申领",
        "失业保险",
        "领取失业保险金|申领失业保险金|失业保险金的手续",
    ),
    (
        "unemployment_duration",
        "失业保险金期限与标准",
        "失业保险",
        "累计缴费|领取失业保险金的期限|领取失业保险金年限|发放标准|满1年的",
    ),
    (
        "unemployment_stop",
        "失业待遇停领、恢复及退回",
        "失业保险",
        "停止领取|停止享受|重新就业|退还|次月起停止|剩余期限",
    ),
    (
        "unemployment_medical",
        "失业期间医疗保险及医疗补助",
        "失业保险",
        "医疗补助|医疗保险|医疗待遇",
    ),
    ("unemployment_funeral", "失业人员遗属待遇", "失业保险", "死亡|丧葬|抚恤"),
    (
        "unemployment_training",
        "失业人员职业培训与职业介绍补贴",
        "失业保险",
        "职业培训|职业介绍|职业技能",
    ),
    (
        "unemployment_self_employed",
        "自谋职业一次性领取剩余失业待遇",
        "失业保险",
        "自谋职业|一次性领取余下",
    ),
    ("unemployment_migrant", "农民合同制工人一次性生活补助", "失业保险", "农民合同制|生活补助"),
    ("unemployment_transfer", "失业保险关系转移", "失业保险", "转迁|跨统筹|关系转移"),
    ("unemployment_2020", "2020年失业补助金申请", "失业保险", "失业补助金"),
    (
        "injury_enroll",
        "工伤保险参保登记与缴费责任",
        "工伤保险",
        "参保登记|工伤保险登记|缴纳工伤保险费|缴费费率|承担工伤保险责任",
    ),
    (
        "injury_report",
        "工伤事故报告与急救",
        "工伤保险",
        "报告经办机构|24小时|及时救治|急救|事故报告",
    ),
    (
        "injury_recognition",
        "工伤认定申请、材料及认定范围",
        "工伤保险",
        "工伤认定|认定为工伤|视同工伤|不予认定",
    ),
    ("injury_assessment", "劳动能力初次鉴定", "工伤保险", "劳动能力鉴定|劳动功能障碍|伤残等级"),
    ("injury_reassessment", "劳动能力复查与再次鉴定", "工伤保险", "复查鉴定|再次鉴定|鉴定结论不服"),
    ("injury_medical", "工伤医疗及手工报销", "工伤保险", "医疗费用|治疗工伤|工伤医疗|费用清单"),
    ("injury_rehab", "工伤康复申请与费用", "工伤保险", "康复"),
    ("injury_device", "工伤辅助器具配置", "工伤保险", "辅助器具|假肢|轮椅"),
    ("injury_leave", "工伤停工留薪与延长确认", "工伤保险", "停工留薪|原工资福利"),
    ("injury_care", "工伤生活护理费", "工伤保险", "生活护理|生活不能自理"),
    ("injury_disability", "工伤伤残补助与伤残津贴", "工伤保险", "伤残津贴|伤残补助金|一次性伤残"),
    (
        "injury_termination",
        "解除劳动关系一次性工伤待遇",
        "工伤保险",
        "伤残就业补助金|一次性工伤医疗补助金|解除劳动合同",
    ),
    ("injury_funeral", "工亡遗属待遇与下落不明", "工伤保险", "工亡|供养亲属|丧葬|下落不明"),
    ("injury_advance", "工伤基金先行支付及追偿", "工伤保险", "先行支付|第三人|用人单位不支付"),
    ("injury_travel", "工伤异地就医与交通食宿补助", "工伤保险", "交通|伙食|住宿|统筹地区以外|食宿"),
    ("injury_stop", "工伤待遇停止、恢复与复发", "工伤保险", "停止享受|停止支付|旧伤复发|工伤复发"),
    (
        "maternity_enroll",
        "生育保险参保与合并征缴",
        "生育保险",
        "缴纳生育保险费|缴费|参保登记|同步参加|合并实施",
    ),
    ("maternity_benefit", "生育保险待遇缴费条件", "生育保险", "享受生育保险待遇|连续为其缴费"),
    ("maternity_allowance", "生育津贴与产假", "生育保险", "生育津贴|产假|流产|引产|分娩"),
    ("maternity_nursing", "男职工护理假与津贴", "生育保险", "护理假"),
    (
        "maternity_medical",
        "生育医疗费用报销与结算",
        "生育保险",
        "生育医疗|生育和计划生育手术医疗|医疗费用|结算",
    ),
    ("family_planning", "计划生育手术费用与休假", "生育保险", "计划生育|节育|绝育|复通"),
    (
        "maternity_spouse",
        "失业女职工与未就业配偶生育待遇",
        "生育保险",
        "未就业配偶|失业的|领取失业保险金",
    ),
    (
        "women_protection",
        "女职工孕期、哺乳期及劳动权益保护",
        "生育保险",
        "劳动保护|劳动合同|月经|怀孕|孕期|哺乳|更年期|性骚扰|妇科|出勤|卫生用品",
    ),
    (
        "housing_deposit",
        "单位公积金缴存登记、开户与汇缴",
        "住房公积金",
        "缴存登记|个人账户设立|汇缴|缴存基数|缴存比例|月缴存额|缴存住房公积金",
    ),
    (
        "housing_defer",
        "降低公积金缴存比例与缓缴",
        "住房公积金",
        "降低缴存比例|降低住房公积金缴存比例|缓缴|缓交",
    ),
    ("housing_arrears", "公积金欠缴补缴", "住房公积金", "补缴|欠缴|少缴"),
    (
        "housing_account",
        "公积金账户变更、封存、启封及合并",
        "住房公积金",
        "信息变更|变更登记|封存|启封|账户合并|账务调整|信息发生变更",
    ),
    (
        "housing_transfer",
        "公积金异地转移接续",
        "住房公积金",
        "转移接续|调往异地|异地转入|异地转移|本地转出",
    ),
    (
        "housing_certificate",
        "公积金缴存证明、查询与复核",
        "住房公积金",
        "缴存证明|有权查询|信息查询|申请受委托银行复核|书面答复",
    ),
    (
        "housing_unit_close",
        "单位公积金缴存登记注销",
        "住房公积金",
        "单位账户注销|缴存登记注销|注销登记",
    ),
    (
        "housing_purchase_withdraw",
        "首套及第二套购房款提取",
        "住房公积金",
        "支付购房款|购房合同提取|购房总价|住房消费类提取|住房套数|套自住房",
    ),
    ("housing_build_withdraw", "建造、翻建、大修自住房提取", "住房公积金", "建造|翻建|大修"),
    (
        "housing_commercial_repay",
        "偿还首套商业或组合贷款提取",
        "住房公积金",
        "偿还个人住房商业贷款|组合贷款中商业贷款|个人住房商业贷款金额",
    ),
    (
        "housing_loan_repay",
        "偿还公积金贷款与委托扣划",
        "住房公积金",
        "偿还住房公积金|委托扣划|归还贷款|贷款归还|提前还款|提前归还|贷款结清",
    ),
    ("housing_rent", "租房公积金提取", "住房公积金", "租赁住房|房租|租房提取|公租房"),
    ("housing_elevator", "加装电梯公积金提取", "住房公积金", "电梯"),
    ("housing_illness", "重大疾病公积金提取", "住房公积金", "重大疾病|重症提取|重症患者"),
    ("housing_disaster", "火灾地震公积金提取", "住房公积金", "火灾|地震|重灾"),
    ("housing_low_income", "低保公积金提取", "住房公积金", "最低生活保障|低保提取"),
    (
        "housing_retire_withdraw",
        "退休公积金销户提取",
        "住房公积金",
        "退休的|销户后不得再开户|社会养老待遇",
    ),
    ("housing_emigration", "出境定居公积金提取", "住房公积金", "出境定居|移民手续|移民签证"),
    ("housing_disability_withdraw", "丧失劳动能力公积金销户提取", "住房公积金", "完全丧失劳动能力"),
    ("housing_job_exit", "离职封存公积金销户提取", "住房公积金", "终止劳动关系|封存停缴"),
    ("housing_inheritance", "死亡公积金继承提取", "住房公积金", "死亡|继承人|受遗赠人"),
    (
        "housing_withdraw_procedure",
        "公积金提取材料、代办与审核",
        "住房公积金",
        "提取业务|提取申请|提取证明|基本材料|专项材料|委托公证|准予提取|全部材料",
    ),
    ("housing_new_loan", "新建商品房公积金贷款", "住房公积金", "新建房|新建商品房|公积金贷款"),
    ("housing_existing_loan", "存量房公积金贷款", "住房公积金", "存量房|评估基准日|买卖双方"),
    (
        "housing_foreign_loan",
        "异地缴存职工公积金贷款",
        "住房公积金",
        "异地贷款|异地公积金贷款|缴存城市|电子码",
    ),
    ("housing_conversion_loan", "商业贷款转公积金贷款", "住房公积金", "商转公|转贷人|原商贷"),
    (
        "housing_loan_change",
        "公积金贷款合同变更与担保",
        "住房公积金",
        "合同变更|变更协议|变更保证人|变更贷款|抵押注销|提供担保|抵押登记",
    ),
    (
        "flex_housing_enroll",
        "灵活就业公积金协议与账户设立",
        "住房公积金",
        "灵活就业人员|灵缴个人账户|签订协议",
    ),
    (
        "flex_housing_pay",
        "灵活就业公积金缴存与账户转换",
        "住房公积金",
        "自由缴存|一次性缴存|按月扣划缴存|账户转换|单位个人账户",
    ),
    (
        "flex_housing_withdraw",
        "灵活就业公积金部分及销户提取",
        "住房公积金",
        "部分提取|销户提取|自由提取|利息补贴|缴存补贴",
    ),
    (
        "flex_housing_loan",
        "灵活就业公积金首套住房贷款",
        "住房公积金",
        "日均缴存余额|灵活就业人员申请|灵活就业人员住房公积金个人贷款|贷款资格",
    ),
    (
        "shared_registration",
        "社会保险统一登记",
        "共享经办",
        "社会保险登记|社会保障号码|公民身份号码",
    ),
    ("shared_change", "社会保险信息变更与注销", "共享经办", "注销社会保险登记|变更|参保信息"),
    ("shared_transfer", "跨险种及军人保险关系转移", "共享经办", "关系转移|转移接续|军人保险"),
    ("shared_query", "参保权益记录查询与核对", "共享经办", "查询|核对|咨询|个人权益记录"),
    ("shared_card", "社会保障卡与医保电子凭证", "共享经办", "社会保障卡|医保电子凭证"),
    (
        "shared_qualification",
        "待遇资格核验、停发告知与多领退回",
        "共享经办",
        "资格|停止发放|停止享受|多享受|退回|还款协议",
    ),
    (
        "shared_complaint",
        "社会保险投诉举报与权益救济",
        "共享经办",
        "举报|投诉|行政复议|行政诉讼|仲裁|申辩|争议",
    ),
    (
        "shared_collection",
        "社会保险征缴、追缴与延期缴费",
        "共享经办",
        "征收|欠缴|滞纳金|延期缴费|申报|缴纳社会保险费",
    ),
    ("shared_privacy", "社会保险个人信息保护", "共享经办", "个人隐私|信息安全|保密|泄露|数据安全"),
    (
        "shared_service",
        "经办渠道、代办与无障碍服务",
        "共享经办",
        "服务渠道|政府网站|移动终端|窗口|代办|无障碍|上门服务|经办服务",
    ),
    (
        "shared_governance",
        "制度范围、基金管理及执行职责",
        "共享经办",
        "基金|财政|监督|管理|职责|原则|施行|实施|解释|制定",
    ),
]


def _evidence(unit: dict, quote: str | None = None) -> dict:
    return {k: unit[k] for k in ("source_path", "title", "article")} | {
        "unit_id": unit["id"],
        "quote": quote if quote is not None else unit["text"],
    }


def field(id, label, type="boolean", role="applicant", **kwargs):
    return {"id": id, "label": label, "type": type, "role": role, "mutable": False, **kwargs}


def cmp(id, op="eq", value=True):
    return {"op": op, "left": {"field": id}, "right": {"value": value}}


def all_of(*conditions):
    return {"all": list(conditions)}


def any_of(*conditions):
    return {"any": list(conditions)}


def _find(units, filename, article, contains="", title_contains=""):
    matches = [
        u
        for u in units
        if (
            Path(u["source_path"]).name.startswith(filename)
            if filename.endswith("_")
            else Path(u["source_path"]).name == filename
        )
        and u["article"].startswith(article)
        and contains in u["text"]
        and title_contains in u["title"]
    ]
    if not matches:
        # Small fixture/user corpora need not contain the bundled rule pack's sources.
        if not any(Path(u["source_path"]).name.startswith(filename) for u in units):
            return None
        raise ValueError(f"规则包来源定位失败: {filename}/{title_contains}/{article}/{contains}")
    if len(matches) != 1:
        raise ValueError(f"规则包来源不唯一: {filename}/{title_contains}/{article}/{contains}")
    return matches[0]


def make_catalog(units):
    matters = {
        id: {
            "id": id,
            "name": name,
            "category": category,
            "description": "依据库内政策提供条款检索；执行能力以已核对规则和已知时空范围为准。",
            "fields": [],
            "policy_parameters": {},
            "rule_ids": [],
            "action_ids": [],
            "goals": [],
            "capabilities": {
                "retrievable": True,
                "checkable": False,
                "simulatable": False,
                "repairable": False,
            },
            "gaps": [],
            "source_unit_ids": [],
        }
        for id, name, category, terms in TOPICS
    }
    rules, actions, coverage = [], [], []
    coverage_by_unit = {}
    for unit in units:
        text = unit["text"]
        if unit["article"] == "发布说明" or (
            re.fullmatch(r"第[一二三四五六七八九十百]+章[^\n]*", text)
        ):
            row = {
                "unit_id": unit["id"],
                "matter_ids": [],
                "disposition": "excluded",
                "reason": f"发布说明或独立章节标题，保留来源与版本信息：{text[:90]}",
            }
        else:
            # Shared clauses apply across branches; sector clauses stay in their actual chapter.
            ids = [
                id
                for id, _, category, terms in TOPICS
                if (category == unit["category"] or category == "共享经办")
                and re.search(terms, text)
            ]
            if not ids:
                ids = ["shared_governance"]
            row = {
                "unit_id": unit["id"],
                "matter_ids": ids,
                "disposition": "mapped",
                "reason": "按条款中的办理对象、行为与制度职责映射；映射不代表规则已启用。",
            }
            for id in ids:
                matters[id]["source_unit_ids"].append(unit["id"])
        coverage.append(row)
        coverage_by_unit[unit["id"]] = row

    def add(id, matter_id, label, source, condition, fields, quote=None):
        unit = _find(units, *source)
        if unit is None:
            return None
        if quote is not None and quote not in unit["text"]:
            raise ValueError(f"规则引用并非原文: {id}")
        matter = matters[matter_id]
        for item in fields:
            if item["id"] not in {f["id"] for f in matter["fields"]}:
                matter["fields"].append(deepcopy(item))
        matter["rule_ids"].append(id)
        if unit["id"] not in matter["source_unit_ids"]:
            matter["source_unit_ids"].append(unit["id"])
        row = coverage_by_unit[unit["id"]]
        if matter_id not in row["matter_ids"]:
            row["matter_ids"].append(matter_id)
        row["disposition"] = "mapped"
        reviewed_hash = SOURCE_REVIEW_MANIFEST.get(unit["source_path"])
        source_reviewed = bool(reviewed_hash and unit.get("source_sha256") == reviewed_hash)
        rules.append(
            {
                "id": id,
                "matter_id": matter_id,
                "label": label,
                "condition": condition,
                "action_id": None,
                "scope": {
                    k: unit[k]
                    for k in (
                        "region",
                        "valid_from",
                        "valid_to",
                        "validity_known",
                        "title",
                        "version",
                    )
                },
                "evidence": [_evidence(unit, quote)],
                "status": "active" if source_reviewed else "candidate",
                "review_source": "implementation_source_review"
                if source_reviewed
                else "source_changed_requires_review",
                "reviewed_source_sha256": reviewed_hash,
                "validation_errors": []
                if source_reviewed
                else [
                    "来源文件不再匹配初始核对版本；固定条件与动作语义必须重新核对，不能直接启用旧阈值。"
                ],
            }
        )
        return rules[-1]

    _reviewed_rules(add)
    _housing_loan_conditions(add)
    _service_actions(add, matters, actions)
    binding = {
        "medical_abroad_direct": "medical_abroad_settled",
        "newborn_free_first_year": "newborn_medical_apply_free",
        "newborn_retroactive": "newborn_medical_birth_coverage",
        "injury_no_exclusion": "injury_recognition_recognized",
        "injury_travel_authorization": "injury_travel_authorized",
        "maternity_claim_record": "maternity_allowance_submit",
        "maternity_allowance_contributions": "maternity_allowance_submit",
        "maternity_medical_contributions": "maternity_medical_submit",
        "maternity_medical_provider": "maternity_medical_submit",
        "housing_deposit_ratio": "housing_deposit_remit",
        "housing_ratio_equal": "housing_deposit_remit",
        "pregnancy_night_work": "women_protection_arrange_work",
    }
    action_ids = {a["id"] for a in actions}
    for rule in rules:
        if rule["action_id"] is None:
            rule["purpose"] = "condition_check"
            id = binding.get(rule["id"], rule["matter_id"] + "_apply")
            rule["action_id"] = id if id in action_ids else None
        else:
            rule["purpose"] = "workflow"
        rule["supported_capabilities"] = (
            (["checkable"] + (["simulatable", "repairable"] if rule["action_id"] else []))
            if rule["status"] == "active"
            else []
        )

    for action in actions:
        pending = [
            r
            for r in rules
            if r["matter_id"] == action["matter_id"]
            and r.get("action_id") in (None, action["id"])
            and r["status"] != "active"
        ]
        action["status"] = "candidate" if pending else "active"
        action["review_source"] = (
            "source_changed_requires_review" if pending else "implementation_source_review"
        )

    reviewed_units = {e["unit_id"] for r in rules if r["status"] == "active" for e in r["evidence"]}
    for unit in units:
        row = coverage_by_unit[unit["id"]]
        row["structured"] = unit["id"] in reviewed_units
        row["structuring_status"] = "partially_reviewed" if row["structured"] else "unstructured"
        row["rule_ids"] = [
            r["id"] for r in rules if any(e["unit_id"] == unit["id"] for e in r["evidence"])
        ]
    unit_index = {u["id"]: u for u in units}
    active = {r["id"] for r in rules if r["status"] == "active"}
    for matter in matters.values():
        changed_sources = sorted(
            {
                unit_index[uid]["source_path"]
                for uid in matter["source_unit_ids"]
                if unit_index[uid].get("source_sha256")
                != SOURCE_REVIEW_MANIFEST.get(unit_index[uid]["source_path"])
                or unit_index[uid]["source_path"] not in SOURCE_REVIEW_MANIFEST
            }
        )
        has_rules = bool(active.intersection(matter["rule_ids"])) and not changed_sources
        has_actions = bool(matter["action_ids"]) and not changed_sources
        matter["capabilities"].update(
            checkable=has_rules,
            simulatable=has_actions,
            repairable=has_actions,
        )
        matter["capability_support"] = {
            "retrievable": list(matter["source_unit_ids"]),
            "checkable": [id for id in matter["rule_ids"] if id in active] if has_rules else [],
            "simulatable": list(matter["action_ids"]) if has_actions else [],
            "repairable": list(matter["action_ids"]) if has_actions else [],
        }
        if changed_sources:
            matter["gaps"].append(
                "来源版本与初始核对清单不一致，执行能力暂停，必须重新核对："
                + "；".join(changed_sources)
            )
        if not has_rules:
            matter["gaps"].append("本事项已有来源条款，尚未核对为可执行条件；当前仅支持检索。")
        else:
            matter["gaps"].append("已核对规则仅覆盖所列条件，不代表完整受理或审批结论。")
            if matter["action_ids"]:
                matter["gaps"].append(
                    "流程目标仅指所选动作：提交申请不等于资格或金额获批，记录审批不等于模拟作出审批；修复只调整动作顺序。"
                )
        if matter["id"] in {
            "housing_new_loan",
            "housing_existing_loan",
            "flex_housing_loan",
            "housing_foreign_loan",
        }:
            matter["gaps"].append(
                "贷款信用审核标准、申请日额度和首付比例、家庭房产记录规则及退休边界需对应配套依据或外部核查；本包不计算最终可贷金额。"
            )
            matter["gaps"].append(
                "库内贷款细则与办事指南存在还贷比例、灵缴倍数/系数及退休年龄口径差异；分别保留版本，不合并为当前标准。"
            )
        unknown = sorted(
            {
                unit_index[id]["title"]
                for id in matter["source_unit_ids"]
                if not unit_index[id]["validity_known"]
            }
        )
        if unknown:
            matter["gaps"].append(
                "以下规范缺少可确认的施行日期，不能据抓取日期认定适用范围：" + "；".join(unknown)
            )
        unstructured = [
            unit_index[id] for id in matter["source_unit_ids"] if id not in reviewed_units
        ]
        if unstructured:
            matter["gaps"].append(
                f"尚有{len(unstructured)}个来源单元未结构化，例如："
                + "；".join(f"{u['title']}·{u['article']}" for u in unstructured[:3])
                + "。完整逐条状态见覆盖清单。"
            )
        if matter["source_unit_ids"]:
            texts = "\n".join(unit_index[id]["text"] for id in matter["source_unit_ids"])
            if re.search("另行|当年|上年度|适时调整|公布的标准|有关规定|相关规定", texts):
                matter["gaps"].append(
                    "部分条款依赖年度标准、目录或另行规定；缺失配套参数时保留 unknown，不用历史值推断当前标准。"
                )
            if re.search("审核|认定|鉴定|核实|批准|审批", texts):
                matter["gaps"].append(
                    "认定、鉴定、联网核实及审批结果须由外部已确认事实提供，模拟动作不能产生这些结果。"
                )
    return [m for m in matters.values() if m["source_unit_ids"]], rules, actions, coverage


def _reviewed_rules(add):
    age = field("age", "申请时周岁年龄", "number")
    add(
        "resident_pension_age",
        "resident_pension_enroll",
        "居民养老参保最低年龄16周岁",
        ("01_", "一、参保范围"),
        cmp("age", "gte", 16),
        [age],
    )
    add(
        "resident_pension_location",
        "resident_pension_enroll",
        "户籍地参保或未就业港澳台居民持居住证在居住地参保",
        ("01_", "一、参保范围"),
        any_of(
            cmp("pension_at_household"),
            all_of(cmp("hmt_residence_permit"), cmp("hmt_unemployed"), cmp("pension_at_residence")),
        ),
        [
            field("pension_at_household", "是否在户籍地申请居民养老参保"),
            field("hmt_residence_permit", "是否为在内地居住且已办理港澳台居民居住证的居民"),
            field("hmt_unemployed", "港澳台居民是否未就业"),
            field("pension_at_residence", "是否在居住地申请"),
        ],
    )
    add(
        "resident_pension_status",
        "resident_pension_enroll",
        "居民养老参保排除在校、机关事业和职工养老覆盖人员",
        ("01_", "一、参保范围"),
        all_of(
            cmp("student", value=False),
            cmp("public_employee", value=False),
            cmp("employee_pension_covered", value=False),
        ),
        [
            field("student", "是否在校学生"),
            field("public_employee", "是否机关事业单位工作人员"),
            field("employee_pension_covered", "是否属于职工养老制度覆盖范围"),
        ],
    )
    add(
        "resident_pension_receipt",
        "resident_pension_benefit",
        "普通缴费人员居民养老待遇领取条件",
        ("01_", "五、待遇领取条件"),
        all_of(
            cmp("age", "gte", 60),
            cmp("resident_pension_years", "gte", 15),
            cmp("other_pension", value=False),
            cmp("other_pension_paying", value=False),
        ),
        [
            age,
            field("resident_pension_years", "累计居民养老缴费年限", "number"),
            field("other_pension", "是否已领取其他国家规定基本养老待遇"),
            field("other_pension_paying", "是否正在其他基本养老保险缴费"),
        ],
    )
    add(
        "resident_pension_transfer_condition",
        "resident_pension_transfer",
        "缴费期间迁移户籍且尚未领取待遇可申请转移",
        ("01_", "（一）转移接续"),
        all_of(cmp("household_moved"), cmp("receiving_pension", value=False)),
        [
            field("household_moved", "缴费期间是否跨地区迁移户籍"),
            field("receiving_pension", "是否已按规定领取居民养老待遇"),
        ],
    )
    add(
        "pension_transfer_not_receiving",
        "pension_transfer",
        "已经领取基本养老待遇的人员不再转移",
        ("17_", "第二条"),
        cmp("receiving_pension", value=False),
        [field("receiving_pension", "是否已经领取国家规定基本养老待遇")],
    )
    add(
        "pension_transfer_acceptance",
        "pension_transfer",
        "养老关系转入年龄、户籍、调动或待遇领取地分支",
        ("18_", "二、受理条件"),
        any_of(
            all_of(cmp("sex", value="男"), cmp("age", "lt", 50)),
            all_of(cmp("sex", value="女"), cmp("age", "lt", 40)),
            cmp("returning_home"),
            cmp("official_transfer"),
            cmp("benefit_location_confirmed"),
        ),
        [
            age,
            field("sex", "性别", "enum", options=["男", "女"]),
            field("returning_home", "是否返回户籍所在地就业参保"),
            field("official_transfer", "县级以上组织或人社部门是否已批准调动", role="external"),
            field(
                "benefit_location_confirmed",
                "是否已确认符合第四项待遇领取地归集条件",
                role="external",
            ),
        ],
    )
    add(
        "retirement_flexible_limit",
        "retirement",
        "弹性退休距法定退休年龄最长三年（单项限制）",
        ("全国人民代表大会常务委员会关于实施渐进式延迟法定退休年龄的决定.txt", "第三条"),
        cmp("flexible_years", "lte", 3),
        [field("flexible_years", "申请提前或延迟年数", "number")],
    )
    add(
        "medical_no_duplicate",
        "employee_medical_enroll",
        "基本医疗保险不得重复参保",
        ("03_", "第八条"),
        cmp("duplicate_medical", value=False),
        [field("duplicate_medical", "是否存在重复基本医保参保")],
    )
    add(
        "medical_flex_wait",
        "medical_pay",
        "灵活就业人员缴费满六个月后的次月享受待遇（单项条件）",
        ("03_", "第十八条"),
        all_of(cmp("medical_paid_months", "gte", 6), cmp("following_month_reached")),
        [
            field("medical_paid_months", "灵活就业医保按规定缴费月数", "number"),
            field("following_month_reached", "是否已进入缴费满六个月后的次月"),
        ],
    )
    add(
        "newborn_free_first_year",
        "newborn_medical",
        "新生儿出生当年免缴费的父母参保条件",
        ("04_", "第九条"),
        cmp("parent_wuhan_medical_paid"),
        [field("parent_wuhan_medical_paid", "父母任一方是否在武汉参加基本医保并按规定缴费")],
    )
    add(
        "newborn_retroactive",
        "newborn_medical",
        "出生九十日内登记或缴费享受出生起待遇",
        ("04_", "第十八条"),
        cmp("newborn_registration_days", "lte", 90),
        [field("newborn_registration_days", "出生至参保登记或缴费天数", "number")],
    )
    add(
        "medical_abroad_direct",
        "medical_abroad",
        "异地直接结算须备案且就医定点机构已开通异地结算",
        ("03_", "第二十五条"),
        all_of(cmp("medical_filing_confirmed"), cmp("direct_settlement_enabled")),
        [
            field("medical_filing_confirmed", "异地就医备案是否已办妥", role="external"),
            field("direct_settlement_enabled", "就医定点机构是否已开通异地结算", role="external"),
        ],
    )
    add(
        "medical_foreign_excluded",
        "medical_exclusion",
        "境外医疗费用不纳入基本医保支付",
        ("03_", "第二十三条"),
        cmp("medical_overseas", value=False),
        [field("medical_overseas", "医疗费用是否发生于境外")],
    )
    add(
        "medical_account_exclusions",
        "medical_account",
        "个人账户不得用于公共卫生、健身养生或非医保范围项目",
        ("05_", "第九条"),
        all_of(
            cmp("public_health", value=False),
            cmp("fitness_wellness", value=False),
            cmp("excluded_medical_item", value=False),
        ),
        [
            field("public_health", "是否属于公共卫生费用"),
            field("fitness_wellness", "是否属于健身养生消费"),
            field("excluded_medical_item", "是否属于国家规定医保不支付项目", role="external"),
        ],
    )
    add(
        "aid_after_insurance",
        "aid_hospital",
        "住院医疗救助实行先保险后救助",
        ("06_", "（四）增强医疗救助托底保障功能"),
        all_of(
            cmp("basic_medical_settled"),
            cmp("serious_medical_settled"),
            cmp("aid_identity_confirmed"),
        ),
        [
            field("basic_medical_settled", "基本医保是否已支付结算", role="external"),
            field("serious_medical_settled", "大病保险等是否已完成结算", role="external"),
            field("aid_identity_confirmed", "是否处于已认定的医疗救助待遇享受期", role="external"),
        ],
    )
    add(
        "unemployment_contributions",
        "unemployment_benefit",
        "失业保险金缴费义务满一年",
        ("21_", "第二十一条"),
        cmp("unemployment_years", "gte", 1),
        [field("unemployment_years", "单位及本人按规定失业保险缴费年限", "number")],
    )
    add(
        "unemployment_other_conditions",
        "unemployment_benefit",
        "非本人意愿失业、已登记且有求职要求",
        ("21_", "第二十一条"),
        all_of(
            cmp("involuntary_unemployment"), cmp("unemployment_registered"), cmp("seeking_work")
        ),
        [
            field("involuntary_unemployment", "是否非因本人意愿中断就业"),
            field("unemployment_registered", "是否已办理失业登记", role="external"),
            field("seeking_work", "是否有求职要求"),
        ],
    )
    add(
        "unemployment_self_business",
        "unemployment_self_employed",
        "自谋职业一次性申领需在领取期且持有效证件",
        ("21_", "第二十六条"),
        all_of(cmp("receiving_unemployment"), cmp("self_employment_proof")),
        [
            field("receiving_unemployment", "是否正在领取失业保险金"),
            field("self_employment_proof", "是否持营业执照或外出务工许可证等有效证件"),
        ],
    )
    add(
        "unemployment_training_certificate",
        "unemployment_training",
        "职业培训补贴需要职业资格或技能等级证书",
        ("社会保险经办条例.txt", "第二十四条"),
        any_of(cmp("qualification_certificate"), cmp("skill_certificate")),
        [
            field("qualification_certificate", "是否有职业资格证书"),
            field("skill_certificate", "是否有职业技能等级证书"),
        ],
    )
    add(
        "injury_employer_deadline",
        "injury_recognition",
        "单位工伤认定申请三十日时限，特殊延长须外部同意",
        ("09_", "第四条"),
        any_of(
            cmp("injury_applicant", "ne", "单位"),
            cmp("injury_days", "lte", 30),
            cmp("extension_confirmed"),
        ),
        [
            field("injury_days", "事故或职业病诊断至单位申请的天数", "number"),
            field(
                "injury_applicant",
                "工伤认定申请主体",
                "enum",
                options=["单位", "职工", "近亲属", "工会"],
            ),
            field("extension_confirmed", "主管部门是否已同意本次申请时限延长", role="external"),
        ],
    )
    add(
        "injury_individual_deadline",
        "injury_recognition",
        "单位未按时申请时职工、近亲属或工会可于一年内申请",
        ("09_", "第五条"),
        any_of(
            cmp("injury_applicant", value="单位"),
            all_of(cmp("employer_did_not_apply"), cmp("within_injury_year")),
        ),
        [
            field(
                "injury_applicant",
                "工伤认定申请主体",
                "enum",
                options=["单位", "职工", "近亲属", "工会"],
            ),
            field("employer_did_not_apply", "用人单位是否未在规定时限内申请"),
            field("within_injury_year", "申请日期是否在事故或职业病诊断之日起一年内（按日历周年）"),
        ],
    )
    add(
        "injury_materials",
        "injury_recognition",
        "工伤认定须申请表、劳动人事关系证明和诊断证明",
        ("09_", "第六条"),
        all_of(cmp("injury_application_form"), cmp("employment_proof"), cmp("diagnosis_proof")),
        [
            field("injury_application_form", "工伤认定申请表是否填写完整", mutable=True),
            field("employment_proof", "是否持劳动或人事关系证明"),
            field("diagnosis_proof", "是否持医疗或职业病诊断证明"),
        ],
    )
    add(
        "injury_no_exclusion",
        "injury_recognition",
        "故意犯罪、醉酒吸毒、自残自杀不得认定工伤（排除条件）",
        ("22_", "第二十二条"),
        all_of(
            cmp("intentional_crime", value=False),
            cmp("intoxication_drugs", value=False),
            cmp("self_harm", value=False),
        ),
        [
            field("intentional_crime", "故意犯罪是否已被有权机关确认", role="external"),
            field("intoxication_drugs", "醉酒或吸毒是否已被有权机关确认", role="external"),
            field("self_harm", "自残或自杀是否已被有权机关确认", role="external"),
        ],
    )
    add(
        "injury_assessment_materials",
        "injury_assessment",
        "劳动能力鉴定需要认定决定、完整病历及有效身份证明",
        ("22_", "第二十八条"),
        all_of(
            cmp("injury_decision_confirmed"),
            cmp("complete_medical_records"),
            cmp("identity_document"),
            cmp("committee_other_materials_confirmed"),
        ),
        [
            field("injury_decision_confirmed", "是否已有工伤认定决定", role="external"),
            field("complete_medical_records", "诊断及检查检验病历是否完整"),
            field("identity_document", "是否有有效身份证明"),
            field(
                "committee_other_materials_confirmed",
                "是否满足鉴定委员会要求的其他材料",
                role="external",
            ),
        ],
    )
    add(
        "injury_reassessment_deadline",
        "injury_reassessment",
        "不服初次或复查鉴定结论十五日内申请再次鉴定",
        ("22_", "第三十二条"),
        cmp("assessment_delivery_days", "lte", 15),
        [field("assessment_delivery_days", "收到鉴定结论至申请再次鉴定天数", "number")],
    )
    add(
        "injury_travel_authorization",
        "injury_travel",
        "工伤异地医疗康复交通食宿须协议机构意见及经办同意",
        ("11_", "三、异地工伤医疗"),
        all_of(cmp("agreement_provider_opinion"), cmp("injury_travel_approved")),
        [
            field(
                "agreement_provider_opinion",
                "参保地协议机构是否已提出异地就医意见",
                role="external",
            ),
            field("injury_travel_approved", "参保地经办机构是否已同意异地就医", role="external"),
        ],
    )
    add(
        "maternity_contributions",
        "maternity_benefit",
        "武汉生育待遇单位连续缴费满六个月以上",
        ("12_", "第十条"),
        cmp("maternity_months", "gte", 6),
        [field("maternity_months", "单位连续为职工缴纳生育保险月数", "number")],
    )
    for matter in ("maternity_allowance", "maternity_medical", "maternity_nursing"):
        add(
            matter + "_contributions",
            matter,
            "本项生育待遇须单位连续缴费满六个月以上",
            ("12_", "第十条"),
            cmp("maternity_months", "gte", 6),
            [field("maternity_months", "单位连续为职工缴纳生育保险月数", "number")],
        )
    add(
        "maternity_nursing_legal_birth",
        "maternity_nursing",
        "男职工配偶符合法律法规生育可享护理假津贴（单项条件）",
        ("12_", "第十三条"),
        cmp("lawful_birth_confirmed"),
        [field("lawful_birth_confirmed", "配偶生育是否已确认符合法律法规", role="external")],
    )
    add(
        "maternity_medical_provider",
        "maternity_medical",
        "生育就医限指定机构，紧急抢救及批准转诊例外",
        ("12_", "第二十二条"),
        any_of(
            cmp("designated_maternity_provider"), cmp("emergency_rescue"), cmp("transfer_approved")
        ),
        [
            field("designated_maternity_provider", "是否为生育保险定点机构", role="external"),
            field("emergency_rescue", "是否紧急抢救"),
            field("transfer_approved", "经办机构是否已批准转诊转院", role="external"),
        ],
    )
    add(
        "maternity_claim_record",
        "maternity_allowance",
        "申领生育津贴应提供病历资料（材料单项条件）",
        ("社会保险经办条例.txt", "第二十条"),
        cmp("maternity_medical_records"),
        [field("maternity_medical_records", "是否持生育津贴申领病历资料")],
    )
    add(
        "pregnancy_night_work",
        "women_protection",
        "孕满二十八周不得夜班或延长工时",
        ("23_", "第十一条"),
        any_of(
            cmp("pregnancy_weeks", "lt", 28),
            all_of(cmp("night_shift", value=False), cmp("overtime", value=False)),
        ),
        [
            field("pregnancy_weeks", "怀孕周数", "number"),
            field("night_shift", "是否安排夜班"),
            field("overtime", "是否安排延长劳动时间"),
        ],
    )
    add(
        "housing_deposit_ratio",
        "housing_deposit",
        "公积金单位和个人缴存比例须为5至12的整数百分比",
        ("13_", "第十条", "单位和职工住房公积金", "缴存管理办法"),
        cmp("deposit_ratio", "in", list(range(5, 13))),
        [field("deposit_ratio", "拟缴存比例（整数百分比）", "number")],
    )
    add(
        "housing_ratio_equal",
        "housing_deposit",
        "单位与个人公积金缴存比例一致",
        ("13_", "第十条", "单位和职工住房公积金", "缴存管理办法"),
        {"op": "eq", "left": {"field": "unit_ratio"}, "right": {"field": "personal_ratio"}},
        [
            field("unit_ratio", "单位缴存比例", "number"),
            field("personal_ratio", "个人缴存比例", "number"),
        ],
    )
    add(
        "housing_rent_condition",
        "housing_rent",
        "租房提取须无自有住房或具公租房配租资格",
        ("14_", "第七条", "无自有住房", "提取管理实施细则"),
        any_of(cmp("no_owned_housing"), cmp("public_rental_qualified")),
        [
            field("no_owned_housing", "职工及配偶是否无自有住房", role="external"),
            field("public_rental_qualified", "是否已取得公租房配租资格", role="external"),
        ],
    )
    add(
        "housing_rent_exclusion",
        "housing_rent",
        "租房提取当年不得有未结清公积金贷款及第五、六条购房提取",
        ("14_", "第七条", "无自有住房", "提取管理实施细则"),
        all_of(
            cmp("outstanding_housing_loan", value=False),
            cmp("purchase_withdraw_this_year", value=False),
        ),
        [
            field("outstanding_housing_loan", "职工或配偶当年是否有未结清公积金贷款"),
            field("purchase_withdraw_this_year", "当年是否有第五或第六条购房类提取"),
        ],
    )
    add(
        "housing_exit_sealed",
        "housing_job_exit",
        "离职销户提取本市户籍封存24个月、非本市6个月",
        ("14_", "第十条", "封存停缴满24个月", "提取管理实施细则"),
        all_of(
            cmp("employment_terminated"),
            any_of(
                all_of(cmp("wuhan_household"), cmp("sealed_months", "gte", 24)),
                all_of(cmp("wuhan_household", value=False), cmp("sealed_months", "gte", 6)),
            ),
        ),
        [
            field("employment_terminated", "是否已与单位终止劳动关系"),
            field("wuhan_household", "是否武汉户籍"),
            field("sealed_months", "账户封存停缴月数", "number"),
        ],
    )
    add(
        "housing_elevator_filing",
        "housing_elevator",
        "加装电梯提取须建设单位先备案",
        ("14_", "第八条", "项目备案", "提取管理实施细则"),
        cmp("elevator_filed"),
        [field("elevator_filed", "建设单位项目备案是否已完成", role="external")],
    )
    add(
        "housing_elevator_time",
        "housing_elevator",
        "加装电梯费用支出36个月内提取",
        ("14_", "第八条", "项目备案", "提取管理实施细则"),
        cmp("elevator_expense_months", "lte", 36),
        [field("elevator_expense_months", "电梯费用支出至申请的月数", "number")],
    )
    add(
        "housing_new_loan_contributions",
        "housing_new_loan",
        "新建房贷款连续足额缴存六个月且账户正常",
        ("24_", "第四条", "贷款对象", "武汉新建商品房"),
        all_of(cmp("housing_paid_months", "gte", 6), cmp("housing_account_normal")),
        [
            field("housing_paid_months", "按时连续足额缴存月数", "number"),
            field("housing_account_normal", "账户状态是否正常", role="external"),
        ],
    )
    add(
        "housing_existing_relative",
        "housing_existing_loan",
        "直系亲属间存量房交易不得申请存量房贷款",
        ("24_", "第十五条", "直系亲属", "武汉存量房"),
        cmp("direct_relative_transaction", value=False),
        [field("direct_relative_transaction", "买卖双方是否直系亲属")],
    )
    add(
        "housing_foreign_contributions",
        "housing_foreign_loan",
        "异地贷款限单位职工连续正常足额缴存六个月及以上",
        ("25_", "第七条"),
        all_of(
            cmp("unit_employee"), cmp("outside_wuhan_deposit"), cmp("housing_paid_months", "gte", 6)
        ),
        [
            field("unit_employee", "是否单位缴存职工"),
            field("outside_wuhan_deposit", "是否在武汉行政区域外缴存"),
            field("housing_paid_months", "连续正常足额缴存月数", "number"),
        ],
    )
    add(
        "housing_foreign_no_parallel",
        "housing_foreign_loan",
        "借款人与配偶不能同时在缴存城市和武汉申请",
        ("25_", "第五条"),
        cmp("parallel_housing_application", value=False),
        [field("parallel_housing_application", "是否同时向缴存城市和武汉申请公积金贷款")],
    )
    add(
        "flex_housing_pension_months",
        "flex_housing_enroll",
        "灵缴开户须武汉灵活就业养老缴费连续六个月且时长满六个月",
        ("15_", "第六条", "在申请账户设立前", "缴存提取管理实施细则"),
        all_of(cmp("flex_pension_months", "gte", 6), cmp("flex_elapsed_months", "gte", 6)),
        [
            field("flex_pension_months", "武汉灵活就业窗口连续养老缴费月数", "number"),
            field("flex_elapsed_months", "实际缴纳时长（月）", "number"),
        ],
    )
    add(
        "flex_housing_partial",
        "flex_housing_withdraw",
        "灵缴部分提取须自由缴存且本人配偶无未结清公积金贷款",
        ("15_", "第十四条", "部分提取", "缴存提取管理实施细则"),
        all_of(
            cmp("deposit_method", value="自由缴存"), cmp("outstanding_housing_loan", value=False)
        ),
        [
            field("deposit_method", "协议缴存方式", "enum", options=["自由缴存", "一次性缴存"]),
            field("outstanding_housing_loan", "本人及配偶是否有未结清公积金贷款"),
        ],
    )
    add(
        "flex_housing_balance",
        "flex_housing_loan",
        "灵缴贷款申请余额不低于贷款金额3%（单项条件）",
        ("15_", "第十四条", "3%", "缴存使用管理办法"),
        {
            "op": "gte",
            "left": {"field": "housing_balance"},
            "right": {"op": "mul", "args": [{"field": "requested_loan"}, {"value": 0.03}]},
        },
        [
            field("housing_balance", "灵缴个人公积金账户余额", "number"),
            field("requested_loan", "拟申请公积金贷款金额", "number"),
        ],
    )
    add(
        "shared_cancel_paid",
        "shared_change",
        "注销单位社保登记须先结清欠费、滞纳金和罚款",
        ("社会保险经办条例.txt", "第十条"),
        all_of(cmp("insurance_arrears_paid"), cmp("late_fees_paid"), cmp("fines_paid")),
        [
            field("insurance_arrears_paid", "欠缴社保费是否已结清"),
            field("late_fees_paid", "社保滞纳金是否已结清"),
            field("fines_paid", "社保罚款是否已结清"),
        ],
    )


def _housing_loan_conditions(add):
    """Check enumerated application conditions; external standards remain distinct facts."""
    common = [
        (field("age", "借款人周岁年龄", "number"), cmp("age", "gte", 18)),
        (
            field("loan_identity_valid", "借款人及配偶是否持合法有效身份证件"),
            cmp("loan_identity_valid"),
        ),
        (
            field("loan_full_civil_capacity", "借款人及配偶是否具有完全民事行为能力"),
            cmp("loan_full_civil_capacity"),
        ),
        (
            field(
                "loan_retirement_boundary_confirmed",
                "是否已核对借款人及配偶未超过其适用法定退休年龄",
                role="external",
            ),
            cmp("loan_retirement_boundary_confirmed"),
        ),
        (
            field("loan_credit_authorized", "是否同意银行及中心查询借款人和配偶征信"),
            cmp("loan_credit_authorized"),
        ),
        (
            field(
                "loan_credit_standard_confirmed",
                "借款人及配偶是否已按适用信用审核标准核查通过",
                role="external",
            ),
            cmp("loan_credit_standard_confirmed"),
        ),
        (field("loan_stable_income", "借款人及配偶是否有稳定经济收入"), cmp("loan_stable_income")),
        (
            field(
                "loan_repayment_capacity_confirmed",
                "借款人及配偶按时还本付息能力是否已核实",
                role="external",
            ),
            cmp("loan_repayment_capacity_confirmed"),
        ),
        (
            field("outstanding_housing_loan", "借款人及配偶在本市及其他城市是否有未结清公积金贷款"),
            cmp("outstanding_housing_loan", value=False),
        ),
        (
            field("loan_impairing_debt", "借款人及配偶是否有影响偿还能力的其他债务"),
            cmp("loan_impairing_debt", value=False),
        ),
        (
            field(
                "loan_downpayment_standard_confirmed",
                "首付款是否已按申请日适用的规定比例核对",
                role="external",
            ),
            cmp("loan_downpayment_standard_confirmed"),
        ),
        (
            field("loan_guarantee_agreed", "是否同意所购住房抵押或提供中心认可的担保"),
            cmp("loan_guarantee_agreed"),
        ),
        (
            field(
                "loan_other_regulations_confirmed",
                "本条引用的其他公积金贷款规定是否已逐项核实",
                role="external",
            ),
            cmp("loan_other_regulations_confirmed"),
        ),
    ]
    property_conditions = [
        (
            field("loan_house_age", "所购存量房房龄（年）", "number"),
            cmp("loan_house_age", "lte", 30),
        ),
        (
            field("loan_title_clear", "存量房是否权属清晰且无法律纠纷", role="external"),
            cmp("loan_title_clear"),
        ),
        (
            field("loan_residence_right", "存量房是否已设立居住权", role="external"),
            cmp("loan_residence_right", value=False),
        ),
        (
            field("loan_full_ownership", "是否为完全产权成套住宅", role="external"),
            cmp("loan_full_ownership"),
        ),
        (
            field("loan_already_transferred", "产权是否已过户至借款人及配偶名下", role="external"),
            cmp("loan_already_transferred", value=False),
        ),
        (
            field("loan_trade_permitted", "所购存量房是否可在交易市场进行交易", role="external"),
            cmp("loan_trade_permitted"),
        ),
    ]
    for matter, source in [
        ("housing_new_loan", ("24_", "第五条", "贷款条件", "武汉新建商品房")),
        ("housing_existing_loan", ("24_", "第五条", "贷款条件", "武汉存量房")),
        ("housing_foreign_loan", ("25_", "第八条")),
        ("flex_housing_loan", ("15_", "第六条", "需同时满足", "个人住房贷款实施细则")),
    ]:
        pairs = list(common)
        if matter != "flex_housing_loan":
            pairs.append(
                (
                    field(
                        "loan_housing_record_confirmed",
                        "家庭住房套数和贷款记录是否已按适用标准核查",
                        role="external",
                    ),
                    cmp("loan_housing_record_confirmed"),
                )
            )
        if matter in {"housing_new_loan", "housing_existing_loan"}:
            pairs.extend(
                [
                    (
                        field("housing_paid_months", "申请前按时连续正常足额汇缴月数", "number"),
                        cmp("housing_paid_months", "gte", 6),
                    ),
                    (
                        field("housing_balance", "借款人账户余额", "number"),
                        {
                            "op": "gte",
                            "left": {"field": "housing_balance"},
                            "right": {
                                "op": "mul",
                                "args": [{"field": "housing_monthly_deposit"}, {"value": 6}],
                            },
                        },
                    ),
                    (
                        field("housing_monthly_deposit", "借款人月缴存额", "number"),
                        cmp("housing_monthly_deposit", "gt", 0),
                    ),
                ]
            )
        if matter == "housing_foreign_loan":
            pairs.append(
                (
                    field(
                        "loan_property_type",
                        "本次异地贷款房屋类型",
                        "enum",
                        options=["新建商品房", "存量房"],
                    ),
                    any_of(
                        cmp("loan_property_type", value="新建商品房"),
                        cmp("loan_property_type", value="存量房"),
                    ),
                )
            )
            pairs.extend(
                (definition, any_of(cmp("loan_property_type", value="新建商品房"), condition))
                for definition, condition in property_conditions
            )
        if matter == "housing_existing_loan":
            pairs.extend(property_conditions)
            pairs.append(
                (
                    field("loan_related_fraud", "是否通过关联交易套取公积金贷款"),
                    cmp("loan_related_fraud", value=False),
                )
            )
        contract = cmp(
            "loan_contract_months", "lte", 6 if matter == "housing_existing_loan" else 12
        )
        if matter == "housing_foreign_loan":
            contract = any_of(
                all_of(
                    cmp("loan_property_type", value="新建商品房"),
                    cmp("loan_contract_months", "lte", 12),
                ),
                all_of(
                    cmp("loan_property_type", value="存量房"), cmp("loan_contract_months", "lte", 6)
                ),
            )
        pairs.append(
            (
                field(
                    "loan_contract_months",
                    "合同签订（异地新建房为网签）至申请的日历月数，超截止日不得向下取整",
                    "number",
                ),
                contract,
            )
        )
        if matter == "flex_housing_loan":
            pairs.extend(
                [
                    (
                        field("sex", "性别", "enum", options=["男", "女"]),
                        any_of(
                            all_of(cmp("sex", value="男"), cmp("age", "lt", 60)),
                            all_of(cmp("sex", value="女"), cmp("age", "lt", 55)),
                        ),
                    ),
                    (
                        field("flex_account_months", "个人账户设立月数", "number"),
                        cmp("flex_account_months", "gt", 12),
                    ),
                    (
                        field("flex_agreement_complied", "是否已按缴存使用协议履行缴存义务"),
                        cmp("flex_agreement_complied"),
                    ),
                    (
                        field(
                            "flex_withdrawn_last_year", "近一年是否提取过灵活就业期间缴存的公积金"
                        ),
                        cmp("flex_withdrawn_last_year", value=False),
                    ),
                ]
            )
        add(
            matter + "_eligibility",
            matter,
            "逐项核查所列贷款申请条件（配套标准及外部核查须提供）",
            source,
            all_of(*(condition for _, condition in pairs)),
            [definition for definition, _ in pairs],
        )


def _service_actions(add, matters, actions):
    """Explicit source-backed sequences. A recorded external result cannot be simulated into existence."""

    def step(
        matter,
        key,
        label,
        source,
        *,
        after=None,
        documents=None,
        external=None,
        requirements=None,
        goal=True,
        additional_effects=None,
    ):
        id = f"{matter}_{key}"
        conditions, fields = [], []
        if after:
            conditions.append({"completed": f"{matter}_{after}"})
        if documents:
            document_field = f"{matter}_{key}_documents"
            fields.append(field(document_field, f"{label}所需材料", "set", options=documents))
            conditions.extend(cmp(document_field, "contains", item) for item in documents)
        for item in requirements or []:
            definition, condition = item
            fields.append(definition)
            conditions.append(condition)
        if external:
            result_field = id + "_confirmed"
            fields.append(field(result_field, external, role="external"))
            conditions.append(cmp(result_field))
            kind = "external"
        else:
            result_field = id + "_done"
            fields.append(field(result_field, f"是否已{label}", mutable=True))
            kind = "user"
        condition = all_of(*conditions) if conditions else {"value": True}
        rule = add(id + "_rule", matter, label + "的前置条件", source, condition, fields)
        if rule is None:
            return
        rule["action_id"] = id
        actions.append(
            {
                "id": id,
                "matter_id": matter,
                "label": label,
                "preconditions": deepcopy(condition),
                "effects": {result_field: True, **(additional_effects or {})},
                "kind": kind,
                "evidence": deepcopy(rule["evidence"]),
            }
        )
        matters[matter]["action_ids"].append(id)
        if goal:
            matters[matter]["goals"].append(
                {"id": id, "label": label, "condition": {"completed": id}}
            )

    def yes(id, label, role="applicant"):
        return field(id, label, role=role), cmp(id)

    # Social-insurance registration and pension services.
    for matter in ("resident_pension_enroll", "employee_pension_enroll", "shared_registration"):
        step(
            matter,
            "apply",
            "申请社会保险参保登记",
            ("社会保险经办条例.txt", "第六条"),
            documents=["有效身份证件"],
            requirements=[yes("registration_identity_valid", "公民身份号码是否有效")],
        )
        step(
            matter,
            "registered",
            "记录经办机构已完成参保登记",
            ("社会保险经办条例.txt", "第六条"),
            after="apply",
            external="经办机构是否已完成本次社会保险登记",
        )
    step(
        "resident_pension_benefit",
        "apply",
        "提交居民基本养老金领取申请",
        ("社会保险经办条例.txt", "第十八条"),
        requirements=[yes("resident_pension_participant", "是否已参加城乡居民养老保险")],
    )
    step(
        "resident_pension_benefit",
        "verified",
        "记录养老金申请核定结果",
        ("社会保险经办条例.txt", "第十八条"),
        after="apply",
        external="经办机构是否已核定本次养老金申请",
    )
    step(
        "employee_pension_benefit",
        "apply",
        "提交职工基本养老金领取申请",
        ("社会保险经办条例.txt", "第十八条"),
        requirements=[
            yes(
                "retirement_qualification_confirmed",
                "是否已确认达到适用退休年龄及缴费条件",
                "external",
            )
        ],
    )
    step(
        "employee_pension_benefit",
        "verified",
        "记录职工养老金核定结果",
        ("社会保险经办条例.txt", "第十八条"),
        after="apply",
        external="经办机构是否已核定本次职工养老金申请",
    )
    step(
        "pension_transfer",
        "certificate",
        "记录原参保地已出具参保缴费凭证",
        ("18_", "六、办事流程"),
        external="原参保地经办机构是否已出具基本养老保险参保缴费凭证",
    )
    step(
        "pension_transfer",
        "apply",
        "向新参保地提交转移接续申请",
        ("18_", "六、办事流程"),
        after="certificate",
        documents=["基本养老保险参保缴费凭证", "基本养老保险关系转移接续申请表"],
        requirements=[yes("new_pension_relation", "是否已在新就业地建立养老关系并缴费")],
    )
    step(
        "pension_transfer",
        "accepted",
        "记录新参保地已发出转移接续联系函",
        ("18_", "六、办事流程"),
        after="apply",
        external="新参保地是否已审核并发出联系函",
    )
    step(
        "pension_transfer",
        "transferred",
        "记录原参保地已转移关系及资金",
        ("17_", "第八条"),
        after="accepted",
        external="原参保地是否已办理关系和基金转出",
    )
    step(
        "pension_transfer",
        "finished",
        "记录新参保地已办结转入手续",
        ("18_", "六、办事流程"),
        after="transferred",
        external="新参保地是否已收到关系、信息表、基金并办结转入",
    )
    step(
        "resident_pension_transfer",
        "apply",
        "向户籍迁入地申请居民养老关系转移",
        ("01_", "（一）转移接续"),
        requirements=[yes("resident_pension_in_payment", "是否处于居民养老缴费期间")],
    )
    step(
        "resident_pension_transfer",
        "finished",
        "记录居民养老个人账户已转移",
        ("01_", "（一）转移接续"),
        after="apply",
        external="迁入地是否已确认接收个人账户并接续参保",
    )
    for matter in ("pension_funeral", "unemployment_funeral"):
        step(
            matter,
            "apply",
            "遗属申领丧葬补助金和抚恤金",
            ("社会保险经办条例.txt", "第十九条"),
            requirements=[
                yes(matter + "_death_condition", "是否已确认符合本条死亡及参保身份条件", "external")
            ],
        )
        step(
            matter,
            "paid",
            "记录丧葬补助和抚恤金核定发放",
            ("社会保险经办条例.txt", "第十九条"),
            after="apply",
            external="经办机构是否已核定并发放本次遗属待遇",
        )

    # Medical registration, direct settlement, reimbursement and assistance.
    step(
        "resident_medical_enroll",
        "apply",
        "在户籍地或居住地办理居民医保参保",
        ("04_", "第九条"),
        documents=["居民身份证或者户口簿"],
    )
    step(
        "resident_medical_enroll",
        "registered",
        "记录居民医保登记完成",
        ("04_", "第九条"),
        after="apply",
        external="医保经办窗口是否已完成本次居民医保登记",
    )
    step(
        "employee_medical_enroll",
        "apply",
        "向医保经办机构申请职工医保登记",
        ("03_", "第九条"),
        requirements=[
            yes("employee_medical_subject", "是否为本条规定的用人单位或参加职工医保的灵活就业人员")
        ],
    )
    step(
        "employee_medical_enroll",
        "registered",
        "记录职工医保登记完成",
        ("03_", "第九条"),
        after="apply",
        external="医保经办机构是否已完成本次职工医保登记",
    )
    step(
        "newborn_medical",
        "apply",
        "为新生儿办理居民医保登记",
        ("04_", "第九条"),
        requirements=[yes("newborn_identity", "是否已备妥新生儿登记身份信息")],
    )
    step(
        "newborn_medical",
        "registered",
        "记录新生儿医保登记完成",
        ("04_", "第九条"),
        after="apply",
        external="医保经办机构是否已完成新生儿登记",
    )
    step(
        "newborn_medical",
        "apply_free",
        "申请新生儿出生当年免缴费参保",
        ("04_", "第九条"),
        requirements=[yes("newborn_identity", "是否已备妥新生儿登记身份信息")],
    )
    step(
        "newborn_medical",
        "birth_coverage",
        "申请从出生之日起享受当年医保待遇",
        ("04_", "第十八条"),
        requirements=[
            yes("newborn_registration_completed", "是否已完成新生儿登记或缴费", "external")
        ],
    )
    step(
        "medical_abroad",
        "filing",
        "申请异地就医备案",
        ("03_", "第二十五条"),
        requirements=[yes("outside_designated_need", "是否因病需要在统筹范围外定点机构就医")],
    )
    step(
        "medical_abroad",
        "filed",
        "记录异地就医备案完成",
        ("03_", "第二十五条"),
        after="filing",
        external="异地就医备案是否已获经办确认",
    )
    step(
        "medical_abroad",
        "settled",
        "记录备案地医疗费用直接结算",
        ("03_", "第二十五条"),
        after="filed",
        external="备案地定点医疗机构是否已完成直接结算",
    )
    for matter in ("medical_reimbursement", "maternity_medical"):
        step(
            matter,
            "prepare",
            "整理手工报销票据与病历",
            ("社会保险经办条例.txt", "第二十条"),
            documents=["收费票据", "费用清单", "诊断证明", "病历资料"],
        )
        step(
            matter,
            "submit",
            "向经办机构提交手工报销申请",
            ("社会保险经办条例.txt", "第二十条"),
            after="prepare",
            requirements=[yes(matter + "_manual_reason", "是否因特殊情况需要个人手工报销")],
        )
        step(
            matter,
            "settled",
            "记录经办机构审核报销结果",
            ("社会保险经办条例.txt", "第二十条"),
            after="submit",
            external="经办机构是否已审核并办结本次手工报销",
        )
    step(
        "aid_application",
        "prepare",
        "整理医后救助申请资料",
        ("19_", "第二十三条"),
        documents=[
            "身份证",
            "社会救助证",
            "社会保障卡",
            "出院小结",
            "基本医疗保险结算票据",
            "武汉市医疗救助申请审批表",
        ],
        requirements=[
            yes("aid_extra_documents", "适用时是否已备妥门诊重症审批表、经济核对授权及收入财产证明")
        ],
    )
    step(
        "aid_application",
        "submit",
        "治疗终结后向街道乡镇提出医后救助申请",
        ("19_", "第二十三条"),
        after="prepare",
        requirements=[
            yes("aid_treatment_finished", "本次治疗是否已终结"),
            yes("aid_residence_condition", "申请地是否为户籍地或居住满一年所在地"),
        ],
    )
    step(
        "aid_application",
        "reviewed",
        "记录街道审核及五个工作日公示无异议",
        ("19_", "第二十三条"),
        after="submit",
        external="街道是否已审核符合条件且五个工作日公示无异议",
    )
    step(
        "aid_application",
        "approved",
        "记录区级民政部门医后救助审批结果",
        ("19_", "第二十三条"),
        after="reviewed",
        external="区级民政部门是否已批准本次医后救助",
    )
    step(
        "aid_application",
        "paid",
        "记录医后救助资金已支付个人账户",
        ("19_", "第二十七条"),
        after="approved",
        external="财政部门是否已将本次救助资金支付个人账户",
    )
    step(
        "aid_direct",
        "apply",
        "住院时向即时结算窗口申请医疗救助",
        ("19_", "第二十二条"),
        documents=["身份证", "社会救助证"],
        requirements=[
            yes(
                "aid_direct_eligible",
                "是否为本条重点、低收入或建档立卡对象且在救助定点机构就诊",
                "external",
            )
        ],
    )
    step(
        "aid_direct",
        "settled",
        "记录出院时医疗救助即时结算",
        ("19_", "第二十二条"),
        after="apply",
        external="定点医疗机构是否已完成本次救助与个人自付结算",
    )
    step(
        "aid_hospital",
        "apply",
        "申请保险结算后的住院医疗救助",
        ("06_", "（四）增强医疗救助托底保障功能"),
        requirements=[
            yes(
                "aid_eligible_expenses",
                "本次费用是否已确认属定点机构政策范围内自付住院费用",
                "external",
            )
        ],
    )
    step(
        "aid_hospital",
        "paid",
        "记录住院医疗救助核定给付",
        ("06_", "（七）规范经办管理服务"),
        after="apply",
        external="经办机构是否已核定并给付本次住院救助",
    )

    # Unemployment: a genuine registration -> application -> decision sequence.
    step(
        "unemployment_register",
        "termination_proof",
        "记录单位已出具解除或终止劳动关系证明",
        ("中华人民共和国社会保险法.txt", "第五十条"),
        external="用人单位是否已出具解除或终止劳动关系证明",
    )
    step(
        "unemployment_register",
        "register",
        "持劳动关系证明办理失业登记",
        ("中华人民共和国社会保险法.txt", "第五十条"),
        after="termination_proof",
        documents=["终止或者解除劳动关系的证明"],
    )
    step(
        "unemployment_register",
        "registered",
        "记录公共就业服务机构已完成失业登记",
        ("中华人民共和国社会保险法.txt", "第五十条"),
        after="register",
        external="公共就业服务机构是否已完成失业登记",
    )
    step(
        "unemployment_benefit",
        "apply",
        "凭登记及身份证明申请失业保险金",
        ("中华人民共和国社会保险法.txt", "第五十条"),
        documents=["失业登记证明", "个人身份证明"],
    )
    step(
        "unemployment_benefit",
        "decided",
        "记录失业保险金申请办结",
        ("社会保险经办条例.txt", "第二十四条"),
        after="apply",
        external="经办机构是否已核定并办结本次失业保险金申请",
    )
    step(
        "unemployment_training",
        "apply",
        "提交职业培训补贴申请",
        ("社会保险经办条例.txt", "第二十四条"),
        documents=["职业资格证书或者职业技能等级证书"],
    )
    step(
        "unemployment_training",
        "decided",
        "记录职业培训补贴审核结果",
        ("社会保险经办条例.txt", "第二十四条"),
        after="apply",
        external="经办机构是否已审核并办结职业培训补贴",
    )
    step(
        "unemployment_self_employed",
        "apply",
        "提交自谋职业剩余待遇一次性领取申请",
        ("21_", "第二十六条"),
        documents=["营业执照、外出务工许可证等有效证件"],
    )
    step(
        "unemployment_self_employed",
        "approved",
        "记录经办机构核准一次性领取余下待遇",
        ("21_", "第二十六条"),
        after="apply",
        external="经办机构是否已核准本次剩余失业待遇一次性领取",
    )

    # Injury recognition, supplementation, assessment and reimbursement.
    step(
        "injury_recognition",
        "prepare",
        "填写工伤认定申请表并整理证明",
        ("09_", "第六条"),
        documents=["劳动、人事关系证明材料", "医疗诊断或职业病诊断证明"],
        additional_effects={"injury_application_form": True},
    )
    step(
        "injury_recognition",
        "apply",
        "提交工伤认定申请",
        ("09_", "第七条"),
        after="prepare",
        requirements=[yes("injury_jurisdiction", "是否属于申请部门的统筹管辖范围", "external")],
    )
    step(
        "injury_recognition",
        "supplement",
        "按一次性告知补正工伤认定材料",
        ("09_", "第八条"),
        after="apply",
        requirements=[
            yes("injury_supplement_notice", "是否已收到需要补正全部材料的书面告知", "external"),
            yes("injury_supplement_ready", "告知要求的补正材料是否齐备"),
        ],
    )
    step(
        "injury_recognition",
        "accepted",
        "记录工伤认定申请受理决定",
        ("09_", "第八条"),
        after="apply",
        external="主管部门是否已出具工伤认定申请受理决定书",
    )
    step(
        "injury_recognition",
        "decided",
        "记录认定工伤或不予认定决定",
        ("09_", "第十八条"),
        after="accepted",
        external="主管部门是否已作出并出具本次工伤认定决定",
    )
    step(
        "injury_recognition",
        "delivered",
        "记录工伤认定决定已送达",
        ("09_", "第二十二条"),
        after="decided",
        external="工伤认定决定是否已送达当事人与用人单位",
    )
    step(
        "injury_recognition",
        "recognized",
        "记录主管部门已认定为工伤",
        ("09_", "第十九条"),
        after="accepted",
        external="主管部门是否已出具本次认定工伤决定书",
    )
    step(
        "injury_assessment",
        "apply",
        "提交劳动能力鉴定申请及材料",
        ("22_", "第二十八条"),
        documents=["劳动能力鉴定申请表", "认定工伤决定书", "诊断及完整病历材料", "有效身份证明"],
    )
    step(
        "injury_assessment",
        "supplement",
        "补正劳动能力鉴定材料",
        ("22_", "第三十条"),
        after="apply",
        requirements=[
            yes("assessment_supplement_notice", "是否已收到鉴定材料补正告知", "external"),
            yes("assessment_supplement_ready", "补正材料是否已齐备"),
        ],
    )
    step(
        "injury_assessment",
        "conclusion",
        "记录劳动能力鉴定结论",
        ("22_", "第三十条"),
        after="apply",
        external="劳动能力鉴定委员会是否已作出本次鉴定结论",
    )
    step(
        "injury_assessment",
        "delivered",
        "记录劳动能力鉴定结论送达",
        ("22_", "第三十条"),
        after="conclusion",
        external="鉴定结论是否已送达工伤职工及其用人单位",
    )
    step(
        "injury_reassessment",
        "apply",
        "向省级鉴定委员会申请再次鉴定",
        ("22_", "第三十二条"),
        documents=["初次鉴定结论原件和复印件", "第二十八条规定的材料"],
    )
    step(
        "injury_reassessment",
        "conclusion",
        "记录省级劳动能力再次鉴定最终结论",
        ("22_", "第三十二条"),
        after="apply",
        external="省劳动能力鉴定委员会是否已作出再次鉴定最终结论",
    )
    for matter in ("injury_medical", "injury_rehab", "injury_device"):
        step(
            matter,
            "prepare",
            "整理工伤费用手工报销材料",
            ("社会保险经办条例.txt", "第二十二条"),
            documents=["收费票据", "费用清单", "诊断证明", "病历资料"],
        )
        step(
            matter,
            "submit",
            "提交工伤费用手工报销申请",
            ("社会保险经办条例.txt", "第二十二条"),
            after="prepare",
            requirements=[yes(matter + "_manual_reason", "是否因特殊情况由单位或个人申请手工报销")],
        )
        step(
            matter,
            "settled",
            "记录工伤费用审核报销结果",
            ("社会保险经办条例.txt", "第二十二条"),
            after="submit",
            external="经办机构是否已审核并办结本次工伤费用报销",
        )
    step(
        "injury_travel",
        "request",
        "申请工伤异地医疗康复或辅助器具配置",
        ("11_", "三、异地工伤医疗"),
        requirements=[
            yes("agreement_provider_opinion", "参保地协议机构是否已提出意见", "external")
        ],
    )
    step(
        "injury_travel",
        "authorized",
        "记录参保地经办机构同意异地就医",
        ("11_", "三、异地工伤医疗"),
        after="request",
        external="参保地经办机构是否已同意本次异地医疗康复或配置辅助器具",
    )

    # Maternity allowance and nursing allowance retain external decisions.
    step(
        "maternity_allowance",
        "prepare",
        "整理生育津贴申领病历",
        ("社会保险经办条例.txt", "第二十条"),
        documents=["病历资料"],
    )
    step(
        "maternity_allowance",
        "submit",
        "向经办机构申领生育津贴",
        ("社会保险经办条例.txt", "第二十条"),
        after="prepare",
        requirements=[yes("maternity_insured", "是否参加生育保险")],
    )
    step(
        "maternity_allowance",
        "decided",
        "记录生育津贴审核结果",
        ("社会保险经办条例.txt", "第二十条"),
        after="submit",
        external="经办机构是否已审核并办结本次生育津贴申请",
    )
    step(
        "maternity_nursing",
        "apply",
        "单位提交护理假津贴结算申请",
        ("12_", "第二十四条"),
        requirements=[yes("nursing_unit_application", "是否由用人单位提交护理假津贴结算申请")],
    )
    step(
        "maternity_nursing",
        "settled",
        "记录护理假津贴审核结算",
        ("12_", "第二十四条"),
        after="apply",
        external="经办机构是否已完成护理假津贴审核结算",
    )
    step(
        "women_protection",
        "complaint",
        "就女职工劳动权益侵害提出投诉举报",
        ("23_", "第二十二条"),
        requirements=[yes("women_rights_infringed", "是否认为用人单位侵害了女职工合法权益")],
    )
    step(
        "women_protection",
        "mediation",
        "申请劳动人事争议调解",
        ("23_", "第二十二条"),
        requirements=[yes("women_rights_infringed", "是否认为用人单位侵害了女职工合法权益")],
    )
    step(
        "women_protection",
        "arbitration",
        "申请劳动人事争议仲裁",
        ("23_", "第二十二条"),
        requirements=[yes("women_rights_infringed", "是否认为用人单位侵害了女职工合法权益")],
    )
    step(
        "women_protection",
        "arrange_work",
        "安排孕期女职工劳动时间",
        ("23_", "第十一条"),
        requirements=[
            yes(
                "pregnancy_work_other_limits",
                "是否已满足本条禁忌作业、温度、产检及休息等其他劳动保护要求",
            )
        ],
    )

    _housing_service_actions(step, yes)
    _shared_service_actions(step, yes)


def _shared_service_actions(step, yes):
    law = "社会保险经办条例.txt"
    step(
        "shared_change",
        "notify",
        "向经办机构告知发生变化的参保信息",
        (law, "第九条"),
        requirements=[yes("insurance_information_changed", "单位或个人参保信息是否已经发生变化")],
    )
    step(
        "shared_change",
        "verified",
        "记录变更参保信息与共享信息比对核实",
        (law, "第九条"),
        after="notify",
        external="经办机构是否已完成本次参保信息比对核实",
    )
    step(
        "shared_change",
        "apply",
        "申请注销单位社会保险登记",
        (law, "第十条"),
        requirements=[yes("insurance_unit_closing", "本次是否为单位注销社会保险登记")],
    )
    step(
        "shared_change",
        "closed",
        "记录单位社会保险登记注销完成",
        (law, "第十条"),
        after="apply",
        external="经办机构是否已办理本次单位社会保险登记注销",
    )
    for matter in ("shared_query", "pension_account"):
        step(matter, "query", "查询核对本人社会保险缴费和待遇记录", (law, "第三十二条"))
        step(
            matter,
            "received",
            "记录经办机构已提供查询核对结果",
            (law, "第三十二条"),
            after="query",
            external="经办机构是否已提供本次查询核对结果",
        )
    for matter in ("shared_qualification", "unemployment_stop", "injury_stop"):
        step(
            matter,
            "notify",
            "告知已经发生的待遇停止情形",
            (law, "第二十五条"),
            requirements=[yes(matter + "_stop_event", "是否已发生国家规定的停止享受本项待遇情形")],
        )
        step(
            matter,
            "stopped",
            "记录经办机构核实并停止相应待遇",
            (law, "第二十五条"),
            after="notify",
            external="经办机构是否已核实并停止本项社会保险待遇",
        )
    step(
        "shared_qualification",
        "repayment",
        "申请对多享受待遇签订分期退回协议",
        (law, "第四十六条"),
        requirements=[
            yes("overpayment_order_confirmed", "经办机构是否已责令退回多享受待遇", "external"),
            yes("overpayment_lump_sum_difficult", "是否难以一次性退回"),
        ],
    )
    step(
        "shared_qualification",
        "agreement",
        "记录分期退回还款协议已签订",
        (law, "第四十六条"),
        after="repayment",
        external="是否已与经办机构签订本次分期退回协议",
    )
    step(
        "shared_complaint",
        "complaint",
        "举报或投诉违反社会保险规定的行为",
        (law, "第五十一条"),
        requirements=[yes("insurance_violation_alleged", "是否反映违反社会保险法律法规规章的行为")],
    )
    step(
        "shared_complaint",
        "handled",
        "记录主管部门依法处理举报投诉",
        (law, "第五十一条"),
        after="complaint",
        external="主管部门是否已依法处理本次举报投诉",
    )
    for key, label in [("review", "依法申请行政复议"), ("litigation", "依法提起行政诉讼")]:
        step(
            "shared_complaint",
            key,
            label,
            (law, "第五十二条"),
            requirements=[
                yes("insurance_rights_infringed", "是否认为经办机构侵害了自身社会保险权益"),
                yes(
                    "remedy_procedure_confirmed",
                    "相关救济法律规定的期限及受理条件是否已经核实",
                    "external",
                ),
            ],
        )
    for matter, article, label, subject in [
        (
            "medical_transfer",
            "第十三条",
            "申请医保关系转移",
            "是否为跨统筹就业的职工或迁移户籍、经常居住地的居民",
        ),
        (
            "unemployment_transfer",
            "第十四条",
            "申请失业保险关系转移",
            "是否为参加失业保险且跨统筹地区就业的个人",
        ),
        (
            "shared_transfer",
            "第十七条",
            "申请军人保险与社会保险关系转移接续",
            "是否为需要军人保险与社会保险关系接续的人员",
        ),
    ]:
        step(
            matter, "apply", label, (law, article), requirements=[yes(matter + "_subject", subject)]
        )
        step(
            matter,
            "finished",
            "记录经办机构已完成本次关系转移接续",
            (law, "第十六条"),
            after="apply",
            external="经办机构是否已完成并告知本次关系转移接续结果",
        )
    for matter, label in [
        ("injury_device", "辅助器具配置确认"),
        ("injury_leave", "停工留薪期延长确认"),
        ("injury_stop", "工伤旧伤复发确认"),
    ]:
        step(
            matter,
            "confirmation_apply",
            "申请" + label,
            (law, "第二十一条"),
            documents=["诊断证明", "病历资料"],
            requirements=[yes(matter + "_injured_worker", "是否为工伤职工或其用人单位")],
        )
        step(
            matter,
            "confirmed",
            "记录" + label + "结果",
            (law, "第二十一条"),
            after="confirmation_apply",
            external="有权机构是否已经完成本次" + label,
        )
    for matter in ("unemployment_enroll", "injury_enroll", "maternity_enroll"):
        step(
            matter,
            "apply",
            "在单位登记时同步办理本险种社会保险登记",
            (law, "第六条"),
            requirements=[
                yes(matter + "_employer_registration", "用人单位是否正在登记管理机关办理登记")
            ],
        )
        step(
            matter,
            "registered",
            "记录本险种社会保险登记已完成",
            (law, "第六条"),
            after="apply",
            external="经办机构是否已完成本险种社会保险登记",
        )
    step(
        "shared_service", "online", "选择政府网站、移动或自助终端办理社保事务", (law, "第二十九条")
    )
    step("shared_service", "counter", "选择经办窗口现场办理社保事务", (law, "第二十九条"))
    step(
        "shared_service",
        "accessible",
        "申请授权代办或上门等便利服务",
        (law, "第三十条"),
        requirements=[
            yes("accessible_service_need", "是否为老年人、残疾人等需要便利服务的特殊群体")
        ],
    )


def _housing_service_actions(step, yes):
    deposit_title = "缴存管理实施细则"
    step(
        "housing_deposit",
        "register",
        "到受托银行办理单位缴存登记及网上业务开通",
        ("13_", "第五条", "单位缴存登记", deposit_title),
        documents=[
            "法定代表人和单位负责人身份证",
            "单位公积金经办人身份证",
            "网上业务操作员身份证",
            "营业执照或统一社会信用代码证照",
            "单位登记开户申请表",
            "开户法律责任告知书",
            "网上业务服务协议",
        ],
        requirements=[
            yes(
                "housing_deposit_extra_documents",
                "选择委托收款或人力资源服务机构时，是否已备妥相应协议或许可证",
            )
        ],
    )
    step(
        "housing_deposit",
        "registered",
        "记录单位公积金缴存登记完成",
        ("13_", "第五条", "单位缴存登记", deposit_title),
        after="register",
        external="受托银行是否已完成单位缴存登记",
    )
    step(
        "housing_deposit",
        "personal_account",
        "办理职工个人公积金账户设立",
        ("13_", "第六条", "个人账户设立", deposit_title),
        after="registered",
        documents=["经办人员身份证", "新开户职工身份证复印件", "住房公积金汇缴（变更）清册"],
        requirements=[yes("housing_new_employee", "是否为本条单位新录用或新调入职工")],
    )
    step(
        "housing_deposit",
        "remit",
        "向受托银行提交住房公积金汇缴资料",
        ("13_", "第十条", "汇缴", deposit_title),
        after="personal_account",
        documents=["住房公积金汇（补）缴书", "转账支票、现金进账单或者汇票等票据"],
        requirements=[
            yes(
                "housing_remit_change_list",
                "缴存人数或金额变化时是否已备汇缴变更清册或基数调整清册",
            )
        ],
    )
    step(
        "housing_defer",
        "resolution",
        "记录职代会、职工大会或工会通过缓缴申请",
        ("13_", "第十一条", "缓缴", deposit_title),
        external="本单位职代会、职工大会或工会是否已讨论通过",
    )
    step(
        "housing_defer",
        "apply",
        "向分中心申请降低比例或缓缴",
        ("13_", "第十一条", "缓缴", deposit_title),
        after="resolution",
        documents=[
            "单位住房公积金账户缓缴（解除）申请表",
            "讨论通过的书面决议",
            "单位近一年财务报表",
            "经办人身份证",
        ],
        requirements=[
            yes(
                "housing_defer_ground_confirmed",
                "是否已证明符合批准缓缴养老失业、停产或规定亏损等条件之一",
                "external",
            )
        ],
    )
    step(
        "housing_defer",
        "approved",
        "记录公积金中心缓缴审批结果",
        ("13_", "第十一条", "缓缴", deposit_title),
        after="apply",
        external="公积金中心是否已批准本次降低比例或缓缴",
    )
    step(
        "housing_defer",
        "resume",
        "效益好转后申请解除缓缴并补缴",
        ("13_", "第十一条", "缓缴", deposit_title),
        after="approved",
        documents=["单位住房公积金账户缓缴（解除）申请表"],
        requirements=[yes("housing_business_improved", "单位经济效益是否已好转")],
    )
    for matter, article, label, documents in [
        (
            "housing_arrears",
            "第十二条",
            "向受托银行办理公积金补缴",
            ["补缴说明", "住房公积金汇（补）缴书", "住房公积金个人补缴清册"],
        ),
        (
            "housing_account",
            "第十七条",
            "办理职工个人账户信息变更",
            ["职工有效身份证明材料", "职工个人基本信息变更登记表或外籍及港澳台人员登记信息变更表"],
        ),
        (
            "housing_transfer",
            "第十九条",
            "向受托银行申请异地账户转入",
            ["职工身份证", "武汉住房公积金异地转移接续申请表"],
        ),
        (
            "housing_unit_close",
            "第二十二条",
            "向分中心申请单位缴存登记注销",
            ["单位合并或注销的合法证明资料", "法定代表人授权书", "单位住房公积金账户注销登记表"],
        ),
        (
            "housing_certificate",
            "第十四条",
            "开具单位住房公积金缴存证明",
            ["住房公积金经办人身份证"],
        ),
    ]:
        requirements = []
        if matter == "housing_transfer":
            requirements = [
                yes("housing_transfer_relationship", "是否在武汉缴存单位建立劳动关系并已设立账户"),
                yes("housing_transfer_six_months", "是否已在武汉连续正常缴存半年以上"),
            ]
        if matter == "housing_unit_close":
            requirements = [yes("housing_unit_ending", "单位是否合并、分立、撤销、解散或者破产")]
        step(
            matter,
            "apply",
            label,
            ("13_", article, "", deposit_title),
            documents=documents,
            requirements=requirements,
        )
        step(
            matter,
            "finished",
            "记录本次缴存账户业务办结",
            ("13_", article, "", deposit_title),
            after="apply",
            external="分中心或受托银行是否已办结本次申请业务",
        )
    # Each extraction branch uses its own substantive source plus the shared formal review article.
    extraction_title = "提取管理实施细则"
    withdrawals = [
        (
            "housing_purchase_withdraw",
            "第五条",
            "支付首套自住房购房款",
            ["备案购房合同或不动产权证书及适用购房票据"],
        ),
        (
            "housing_commercial_repay",
            "第五条",
            "偿还首套自住房商业贷款",
            ["借款抵押合同", "购房合同、不动产权证书或房查证明"],
        ),
        ("housing_rent", "第七条", "租赁住房", []),
        (
            "housing_elevator",
            "第八条",
            "加装电梯",
            ["房屋所有权证或不动产权证书", "实际支付费用发票或收据"],
        ),
        (
            "housing_illness",
            "第九条",
            "重大疾病",
            [
                "重症患者身份证",
                "市级以上医院诊断证明",
                "医保部门重症病历",
                "住院或适用门诊费用凭证",
            ],
        ),
        ("housing_disaster", "第九条", "火灾地震", ["事故房屋不动产权证书", "灾害佐证材料"]),
        ("housing_low_income", "第九条", "最低生活保障", []),
        ("housing_retire_withdraw", "第十条", "退休销户", []),
        (
            "housing_emigration",
            "第十条",
            "出境定居销户",
            ["户口注销证明或者移民签证（公证翻译件）"],
        ),
        ("housing_disability_withdraw", "第十条", "完全丧失劳动能力销户", []),
        ("housing_job_exit", "第十条", "离职封存销户", []),
        (
            "housing_inheritance",
            "第十一条",
            "死亡继承销户",
            ["死亡法律文件", "继承或受遗赠人身份证明及关系材料"],
        ),
    ]
    for matter, article, label, documents in withdrawals:
        step(
            matter,
            "prepare",
            f"整理{label}提取基本材料",
            ("14_", "第三条", "基本材料", extraction_title),
            documents=["职工本人身份证", "本人I类银行借记卡"],
            requirements=[
                yes(
                    matter + "_marriage_proof",
                    "非销户且涉及婚姻关系时是否已备妥适用婚姻及配偶身份证明",
                )
            ],
        )
        step(
            matter,
            "apply",
            f"提交{label}公积金提取申请",
            ("14_", article, "", extraction_title),
            after="prepare",
            documents=documents,
        )
        step(
            matter,
            "supplement",
            "按告知补正本次提取申请材料",
            ("14_", "第十四条", "全部材料", extraction_title),
            after="apply",
            requirements=[
                yes(matter + "_supplement_notice", "是否已收到本次提取材料补正告知", "external"),
                yes(matter + "_supplement_ready", "告知要求的补正材料是否齐备"),
            ],
        )
        step(
            matter,
            "approved",
            "记录分中心或银行准予提取决定",
            ("14_", "第十四条", "全部材料", extraction_title),
            after="apply",
            external="分中心或受托银行是否已确认条件符合、材料完整、联网核查通过并准予本次提取",
        )
    # Loans: application, bank reviews, center review, signature, mortgage and disbursement.
    for matter, prefix, title, procedure in [
        ("housing_new_loan", "24_", "武汉新建商品房", "第十条"),
        ("housing_existing_loan", "24_", "武汉存量房", "第十条"),
        ("flex_housing_loan", "15_", "个人住房贷款实施细则", "第十二条"),
        ("housing_foreign_loan", "25_", "", "第十一条"),
    ]:
        src = (prefix, procedure, "", title)
        step(
            matter,
            "prepare",
            "整理本次住房公积金贷款申请材料",
            src,
            documents=["身份证及户籍证明", "婚姻状况证明", "购房合同及首付款凭证"],
            requirements=[
                yes(
                    matter + "_loan_extra_materials",
                    "是否按本条房型和身份备齐专项材料及银行中心要求的其他材料",
                )
            ],
        )
        step(matter, "apply", "向受托银行提交贷款申请", src, after="prepare")
        review_source = (prefix, "第十三条", "", title) if prefix == "25_" else src
        step(
            matter,
            "initial",
            "记录受托银行贷款初审通过",
            review_source,
            after="apply",
            external="受托银行是否已确认本次贷款初审通过",
        )
        step(
            matter,
            "secondary",
            "记录受托银行贷款复审通过",
            review_source,
            after="initial",
            external="受托银行是否已确认本次贷款复审通过",
        )
        step(
            matter,
            "final",
            "记录公积金中心贷款终审通过",
            review_source,
            after="secondary",
            external="公积金中心是否已确认本次贷款终审通过",
        )
        sign_source = (prefix, "第十四条", "", title) if prefix == "25_" else src
        step(matter, "sign", "面签借款抵押合同", sign_source, after="final")
        mortgage_source = (prefix, "第十五条", "", title) if prefix == "25_" else src
        step(
            matter,
            "mortgage",
            "记录抵押登记已经办理完成",
            mortgage_source,
            after="sign",
            external="不动产登记机构是否已办妥本次贷款抵押担保手续",
        )
        payment_source = (prefix, "第十六条", "", title) if prefix == "25_" else src
        step(
            matter,
            "payment",
            "记录银行已向指定账户发放贷款",
            payment_source,
            after="mortgage",
            external="受托银行是否已按放款通知或合同向指定账户实际发放本次贷款",
        )
    flex_title = "缴存提取管理实施细则"
    step(
        "flex_housing_enroll",
        "agreement",
        "签订灵活就业住房公积金缴存使用协议",
        ("15_", "第五条", "签订协议", flex_title),
    )
    step(
        "flex_housing_enroll",
        "apply",
        "办理灵缴个人住房公积金账户设立",
        ("15_", "第六条", "个人账户设立", flex_title),
        after="agreement",
        requirements=[yes("flex_single_account", "是否仅维持一个正常住房公积金账户")],
    )
    step(
        "flex_housing_enroll",
        "opened",
        "记录受托银行已设立灵缴个人账户",
        ("15_", "第六条", "个人账户设立", flex_title),
        after="apply",
        external="受托银行是否已完成本次灵缴个人账户设立",
    )
    step(
        "flex_housing_withdraw",
        "apply",
        "申请自由缴存账户部分提取",
        ("15_", "第十四条", "部分提取", flex_title),
        documents=["本人身份证明材料", "本人银行I类借记卡"],
    )
    step(
        "flex_housing_withdraw",
        "finished",
        "记录灵缴账户部分提取办结",
        ("15_", "第十四条", "部分提取", flex_title),
        after="apply",
        external="受托银行是否已办结本次灵缴账户部分提取",
    )
