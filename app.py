"""
FunReserve 潜店信息提取工具
用法：streamlit run app.py
"""

import streamlit as st
import httpx
import json

OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

PROMPT_TEMPLATE = """你是FunReserve潜水预订平台的潜店信息录入助手。
请访问以下链接，抓取该潜水店的所有公开信息，严格按照下方字段结构输出。
找不到的字段统一标注【待补充】，绝对不要编造任何信息。

{links}

请按以下结构输出：

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


def build_links_text(website, instagram="", facebook="", google_maps="", tripadvisor=""):
    lines = []
    if website:
        lines.append(f"潜店网址：{website}")
    if google_maps:
        lines.append(f"Google Maps：{google_maps}")
    if instagram:
        lines.append(f"Instagram：{instagram}")
    if facebook:
        lines.append(f"Facebook：{facebook}")
    if tripadvisor:
        lines.append(f"TripAdvisor：{tripadvisor}")
    return "\n".join(lines)


def extract_missing_fields(content: str) -> list:
    missing = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("MISSING:"):
            field = line.replace("MISSING:", "").strip()
            if field:
                missing.append(field)
    return missing


def call_claude_with_search(links_text: str):
    """调用OpenRouter的Claude，使用web search插件读取网页"""
    prompt = PROMPT_TEMPLATE.format(links=links_text)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://funreserve.com",
        "X-Title": "FunReserve Dive Shop Tool",
    }

    payload = {
        "model": "anthropic/claude-sonnet-4-5",
        "max_tokens": 4000,
        "stream": True,
        "plugins": [{"id": "web"}],  # 开启web搜索插件
        "messages": [{"role": "user", "content": prompt}],
    }

    with httpx.stream(
        "POST",
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    data = json.loads(line[6:])
                    delta = data["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    continue


# ─── UI ──────────────────────────────────────────────────────────

st.set_page_config(page_title="FunReserve 潜店信息提取", layout="wide")
st.title("🤿 FunReserve 潜店信息提取工具")
st.caption("输入潜店链接，AI 自动读取网页并整理所有字段，标注待补充项。")

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

        links_text = build_links_text(website, instagram, facebook, google_maps, tripadvisor)
        result_placeholder = st.empty()
        full_content = ""

        with st.spinner("AI 正在读取网页并分析，请稍候（约1-2分钟）..."):
            try:
                for chunk in call_claude_with_search(links_text):
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
            st.success("所有字段均已获取！")

        st.divider()
        st.download_button(
            label="下载结果（Markdown）",
            data=full_content,
            file_name=f"{website.replace('https://','').replace('http://','').split('/')[0]}.md",
            mime="text/markdown",
        )
