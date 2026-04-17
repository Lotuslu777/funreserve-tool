"""
FunReserve 潜店信息提取工具
用法：streamlit run app.py
"""

import streamlit as st
import httpx
import json

OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# 复杂结构的章节用大文本框展示，其余字段逐条展示
COMPLEX_SECTIONS = {"四、服务项目", "七、潜点", "八、教练团队"}

PROMPT_TEMPLATE = """你是FunReserve潜水预订平台的潜店信息录入助手。
请访问以下所有链接，抓取该潜水店的公开信息，严格按照字段结构输出。
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
"""

SUPPLEMENT_PROMPT = """你是FunReserve潜水预订平台的潜店信息录入助手。
以下是该潜店已有的信息，以及用户补充提供的额外链接/资料。
请访问补充链接，把【待补充】的字段尽量填上，已有内容不要修改。
绝对不要编造任何信息，仍找不到的字段继续标注【待补充】。

已有信息：
{existing}

补充资料：
{supplement}

请按原有格式输出完整的更新后内容。"""


def build_links_text(website, instagram="", facebook="", google_maps="", tripadvisor="") -> str:
    lines = []
    if website:
        lines.append(f"官网：{website}")
    if instagram:
        lines.append(f"Instagram：{instagram}")
    if facebook:
        lines.append(f"Facebook：{facebook}")
    if google_maps:
        lines.append(f"Google Maps：{google_maps}")
    if tripadvisor:
        lines.append(f"TripAdvisor：{tripadvisor}")
    return "\n".join(lines)


def parse_content(content: str) -> list[dict]:
    """把 AI 输出解析成 [{title, is_complex, fields:[{name,value,missing}]}]"""
    sections = []
    current = None

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("## "):
            if current:
                sections.append(current)
            title = line[3:].strip()
            is_complex = any(k in title for k in COMPLEX_SECTIONS)
            current = {"title": title, "is_complex": is_complex, "fields": [], "raw_lines": []}
        elif current is None:
            continue
        elif line.startswith("- ") and "：" in line and not current["is_complex"]:
            parts = line[2:].split("：", 1)
            name = parts[0].strip().strip("*").strip()
            value = parts[1].strip() if len(parts) > 1 else ""
            missing = "【待补充】" in value or value == ""
            if missing:
                value = ""
            current["fields"].append({"name": name, "value": value, "missing": missing})
        else:
            current["raw_lines"].append(line)

    if current:
        sections.append(current)
    return sections


def call_claude(prompt: str):
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
        "plugins": [{"id": "web"}],
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.stream("POST", "https://openrouter.ai/api/v1/chat/completions",
                      headers=headers, json=payload, timeout=120) as resp:
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


def render_fields(sections: list[dict]):
    """渲染各字段，缺失字段标红"""
    st.markdown("""
    <style>
    .missing-label { color: #e53935; font-weight: 600; font-size: 0.85rem; margin-bottom: 2px; }
    .ok-label { color: #444; font-size: 0.85rem; margin-bottom: 2px; }
    </style>
    """, unsafe_allow_html=True)

    collected = {}
    for sec in sections:
        st.subheader(sec["title"])
        if sec["is_complex"]:
            raw_text = "\n".join(sec["raw_lines"])
            val = st.text_area("", value=raw_text, height=200,
                               key=f"sec_{sec['title']}", label_visibility="collapsed")
            collected[sec["title"]] = val
        else:
            for f in sec["fields"]:
                if f["missing"]:
                    st.markdown(f'<div class="missing-label">⚠ {f["name"]}（待补充）</div>',
                                unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="ok-label">{f["name"]}</div>',
                                unsafe_allow_html=True)
                long_field = any(k in f["name"] for k in ["介绍", "Introduction", "描述", "内容", "文案"])
                if long_field:
                    val = st.text_area("", value=f["value"], height=120,
                                       key=f'field_{sec["title"]}_{f["name"]}',
                                       placeholder="待补充...", label_visibility="collapsed")
                else:
                    val = st.text_input("", value=f["value"],
                                        key=f'field_{sec["title"]}_{f["name"]}',
                                        placeholder="待补充...", label_visibility="collapsed")
                collected[f'{sec["title"]}_{f["name"]}'] = val
            if sec["raw_lines"]:
                raw_text = "\n".join(sec["raw_lines"])
                val = st.text_area("", value=raw_text, height=80,
                                   key=f"raw_{sec['title']}", label_visibility="collapsed")
                collected[f'raw_{sec["title"]}'] = val
    return collected


# ─── UI ──────────────────────────────────────────────────────────

st.set_page_config(page_title="FunReserve 潜店信息提取", layout="wide")
st.title("🤿 FunReserve 潜店信息提取工具")
st.caption("输入潜店链接，AI 自动读取网页并整理所有字段，红色字段为待补充项。")

with st.form("input_form"):
    st.subheader("第一步：输入潜店链接")
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
        result_placeholder = st.empty()
        full_content = ""

        with st.spinner("AI 正在读取网页并分析，请稍候（约1-2分钟）..."):
            try:
                links_text = build_links_text(website, instagram, facebook, google_maps, tripadvisor)
                prompt = PROMPT_TEMPLATE.format(links=links_text)
                for chunk in call_claude(prompt):
                    full_content += chunk
                    result_placeholder.markdown(full_content)
            except Exception as e:
                st.error(f"分析失败：{e}")
                st.stop()

        result_placeholder.empty()
        st.session_state["full_content"] = full_content
        st.session_state["website"] = website

# 展示结果
if "full_content" in st.session_state:
    full_content = st.session_state["full_content"]
    website = st.session_state["website"]
    sections = parse_content(full_content)

    st.subheader("第二步：核对并补充字段")
    st.caption("红色字段为 AI 未找到的内容，可直接在输入框中补充。")
    render_fields(sections)

    # 补充更多信息
    st.divider()
    st.subheader("第三步：补充更多资料（可选）")
    st.caption("如有其他网址或文字资料，粘贴在下方，让 AI 继续补充缺失字段。")
    supplement_input = st.text_area(
        "补充链接或文字",
        placeholder="例如：小红书链接、其他官网页面、商家提供的文字资料...",
        height=100,
        label_visibility="collapsed",
    )
    if st.button("AI 继续补充", type="secondary"):
        with st.spinner("AI 正在补充缺失字段..."):
            supplement_prompt = SUPPLEMENT_PROMPT.format(
                existing=full_content,
                supplement=supplement_input,
            )
            new_content = ""
            placeholder2 = st.empty()
            try:
                for chunk in call_claude(supplement_prompt):
                    new_content += chunk
                    placeholder2.markdown(new_content)
                st.session_state["full_content"] = new_content
                st.rerun()
            except Exception as e:
                st.error(f"补充失败：{e}")

    st.divider()
    st.download_button(
        label="下载完整结果（Markdown）",
        data=full_content,
        file_name=f"{website.replace('https://','').replace('http://','').split('/')[0]}.md",
        mime="text/markdown",
    )
