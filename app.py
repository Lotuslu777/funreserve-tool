"""
FunReserve 潜店信息提取工具
用法：streamlit run app.py
"""

import re
import streamlit as st
import httpx
from openai import OpenAI

OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# ─── 字段结构提示词 ───────────────────────────────────────────────
PROMPT_TEMPLATE = """你是FunReserve潜水预订平台的潜店信息录入助手。
以下是从该潜水店各个页面抓取到的原始网页内容，请根据这些内容提取信息，严格按照字段结构输出。
找不到的字段统一标注【待补充】，绝对不要编造任何信息。

{content}

请按以下结构输出，每个字段单独一行：

## 一、基础信息
- 潜店名称：
- 所在国家：
- 详细地址：
- 可服务语言：（从 中文/English/Español/Français/Русский/日本語/한국어/Bahasa Indonesia 中勾选）
- 所属平台认证：（从 PADI/SSI/SDI/TDI 中勾选）
- 营业时间：（周一至周日，注明时间或"休息"）
- 经营年限：（0-3年/3-5年/5-10年/10年以上）
- 支付方式：（从 现金/信用卡/PayPal/微信支付/支付宝 中勾选）

## 二、联系方式
- 客人联系-电话：
- 客人联系-WhatsApp：
- 客人联系-微信：
- 客人联系-邮箱：
- 客人联系-Instagram：
- 客人联系-Facebook：
- 客人联系-Line：
- FunReserve联系-电话：
- FunReserve联系-WhatsApp：
- FunReserve联系-邮箱：

## 三、船只信息
- 是否配备船只：（是/否）
- 船只名称/型号：
- 船只类型：
- 容纳人数：
- 配套设施：（从 空调/淋浴/卫生间/潜水平台/储物间/日光甲板/厨房/Wi-Fi/摄影工作台 中勾选）
- 船只数量：
- 船只介绍（中文150字）：

## 四、服务项目（逐项列出，用---分隔）
每项包含：
- 服务类型：（岸潜/潜水课程/船潜/自由潜/DSD/特殊服务）
- 项目名称（中文）：
- Project Name（English）：
- 服务时长：
- 价格：
- 项目介绍：
- 项目包含内容：
- 项目不包含内容：
- 是否提供保险：
- 附加费用：
- 项目标签：

## 五、装备租赁
- 潜水电脑：
- 运动相机：
- 气瓶：
- 调节器：
- 浮力控制装置：
- 潜水靴&脚蹼：
- 面镜、呼吸管&脚蹼：
- 潜水服：

## 六、配套服务
（从 水下摄影/VIP服务/接送服务/住宿/Wi-Fi/餐食 中勾选）

## 七、潜点（最多5个）
每个潜点：
- 潜点名称：
- 潜点特色：
- 描述：

## 八、教练团队
- 教练人数：
- 教练学员比：
- 潜导人数：
- 潜导学员比：
（逐一列出每位教练/潜导的姓名、从业年限、介绍）

## 九、文案
- 中文介绍（200字）：
- English Introduction（200 words）：

## 十、图片URL
- 潜店外观：
- 潜店内部：
- 船只：
- 水下/潜点：
- 教练团队：

## 十一、待补充字段清单
请在最后用以下格式列出所有【待补充】的字段，每行一个：
MISSING: 字段名称
"""


def fetch_page(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        text = re.sub(r"<style[^>]*>.*?</style>", " ", resp.text, flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:8000]
    except Exception as e:
        return f"[无法访问 {url}：{e}]"


def fetch_all_content(website, instagram="", facebook="", google_maps="", tripadvisor="") -> str:
    parts = []
    urls = {
        "官网": website,
        "Instagram": instagram,
        "Facebook": facebook,
        "Google Maps": google_maps,
        "TripAdvisor": tripadvisor,
    }
    for label, url in urls.items():
        if url:
            parts.append(f"=== {label}：{url} ===\n{fetch_page(url)}")
    return "\n\n".join(parts)


def extract_missing_fields(content: str) -> list[str]:
    missing = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("MISSING:"):
            field = line.replace("MISSING:", "").strip()
            if field:
                missing.append(field)
    return missing


def call_claude(web_content: str):
    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
    prompt = PROMPT_TEMPLATE.format(content=web_content)
    stream = client.chat.completions.create(
        model="anthropic/claude-sonnet-4-5",
        max_tokens=4000,
        stream=True,
        messages=[{"role": "user", "content": prompt}],
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# ─── UI ──────────────────────────────────────────────────────────

st.set_page_config(page_title="FunReserve 潜店信息提取", layout="wide")
st.title("🤿 FunReserve 潜店信息提取工具")
st.caption("输入潜店链接，AI 自动抓取并整理所有字段，标注待补充项。")

with st.form("input_form"):
    st.subheader("输入潜店链接")
    website = st.text_input("官网 URL *", placeholder="https://example.com")
    col1, col2 = st.columns(2)
    with col1:
        instagram = st.text_input("Instagram", placeholder="https://instagram.com/...")
        facebook = st.text_input("Facebook", placeholder="https://facebook.com/...")
    with col2:
        google_maps = st.text_input("Google Maps", placeholder="https://maps.app.goo.gl/...")
        tripadvisor = st.text_input("TripAdvisor", placeholder="https://tripadvisor.com/...")

    submitted = st.form_submit_button("开始分析", type="primary", use_container_width=True)

if submitted:
    if not website:
        st.error("请至少填写官网 URL")
    else:
        st.divider()
        st.subheader("分析结果")

        with st.spinner("正在抓取网页内容..."):
            web_content = fetch_all_content(website, instagram, facebook, google_maps, tripadvisor)

        result_placeholder = st.empty()
        full_content = ""

        with st.spinner("AI 正在分析，请稍候..."):
            try:
                for chunk in call_claude(web_content):
                    full_content += chunk
                    result_placeholder.markdown(full_content)
            except Exception as e:
                st.error(f"分析失败：{e}")
                st.stop()

        missing = extract_missing_fields(full_content)
        st.divider()
        if missing:
            st.subheader(f"⚠️ 待补充字段（共 {len(missing)} 项）")
            st.caption("以下字段在官网未找到，需运营联系商家补充：")
            for field in missing:
                st.markdown(f"- [ ] {field}")
        else:
            st.success("所有字段均已获取，无需补充！")

        st.divider()
        st.download_button(
            label="下载结果（Markdown）",
            data=full_content,
            file_name=f"{website.replace('https://', '').replace('http://', '').split('/')[0]}.md",
            mime="text/markdown",
        )
