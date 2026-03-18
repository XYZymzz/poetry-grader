import streamlit as st
import pandas as pd
import os
import json
import altair as alt
from dotenv import load_dotenv
from openai import OpenAI

# ==========================================
# 准备工作：加载密码并初始化 AI
# ==========================================
load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# ==========================================
# 核心升级 1：定义公共账本（数据持久化）
# ==========================================
DATA_FILE = "class_records.csv"

# 读取历史数据
def load_records():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        # 如果文件不存在，返回一个带表头的空表格
        return pd.DataFrame(columns=["学生姓名", "题目", "学生作答", "判定状态", "错误类型", "AI 详细反馈"])

# 追加保存新数据
def save_record(new_record):
    df = load_records()
    # 将新记录追加到原有数据下方
    new_df = pd.DataFrame([new_record])
    df = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(DATA_FILE, index=False) # 写入硬盘保存

# ==========================================
# 题库与提示词定义
# ==========================================
questions_db = {
    "题目1": {
        "question": "诗中表现梅花不畏严寒、傲然挺立的句子是哪一句？",
        "answer": "凌寒独自开"
    },
    "题目2": {
        "question": "诗人为什么在远处就能知道那不是雪？",
        "answer": "为有暗香来"
    }
}

prompt_template = """
你是一个严谨的语文老师。你的任务是批改学生关于王安石《梅花》的情景默写题。
【题目】：{q}
【标准答案】：{a}
【学生作答】：{s}

请按以下规则批改，并严格只输出 JSON 格式的数据，不要输出任何额外的废话：
1. 如果学生作答与标准答案完全一致，判定为 correct。
2. 如果学生填对了句子，但有错别字，判定为 typo。你需要指出错字、给出正确字。
3. 如果学生句子完全填错，判定为 wrong。你需要给出标准答案，并解释题目。

你的 JSON 输出格式必须严格如下：
{{
  "status": "correct | typo | wrong",
  "feedback": "给学生的反馈话语",
  "error_type": "无错 | 错别字 | 诗句填错"
}}
"""

# ==========================================
# 核心升级 2 & 3：侧边栏路由与权限校验
# ==========================================
st.sidebar.title("⚙️ 系统控制台")
role = st.sidebar.radio("请选择登录身份：", ["👨‍🎓 学生端", "👩‍🏫 教师端"])

# ==========================================
# 核心升级 4：业务逻辑解耦（分发视图）
# ==========================================

if role == "👨‍🎓 学生端":
    st.title("📝 王安石《梅花》自动批改系统")
    st.divider()

    selected_q_id = st.selectbox("请选择你要测试的题目：", list(questions_db.keys()))
    current_q_text = questions_db[selected_q_id]["question"]
    current_standard_answer = questions_db[selected_q_id]["answer"]

    st.markdown(f"### 📌 {selected_q_id} 题目内容：")
    st.success(current_q_text)
    st.caption("👇 请仔细阅读上方题目，并在下方输入你的答案")

    student_name = st.text_input("请输入学生姓名：", placeholder="例如：张三")
    student_answer = st.text_input("请输入你的答案：", placeholder="输入诗句...")

    if st.button("🚀 提交并获取批改"):
        if student_answer.strip() == "" or student_name.strip() == "":
            st.warning("姓名和答案都不能为空哦！请重新输入。")
        else:
            final_prompt = prompt_template.format(
                q=current_q_text, 
                a=current_standard_answer, 
                s=student_answer
            )
            
            with st.spinner("AI 老师正在飞速批改中，请稍候..."):
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat", 
                        messages=[{"role": "user", "content": final_prompt}],
                        response_format={"type": "json_object"}, 
                        temperature=0.1 
                    )
                    
                    ai_result_dict = json.loads(response.choices[0].message.content)
                    
                    # 界面反馈
                    st.success(f"批改完成！成绩已成功上传至教师端。")
                    st.write("✨ **AI 老师给你的专属反馈：**", ai_result_dict.get("feedback"))
                    
                    # 真正写入 CSV 文件
                    new_record = {
                        "学生姓名": student_name,
                        "题目": selected_q_id,
                        "学生作答": student_answer,
                        "判定状态": ai_result_dict.get("status"),
                        "错误类型": ai_result_dict.get("error_type"),
                        "AI 详细反馈": ai_result_dict.get("feedback")
                    }
                    save_record(new_record)
                    
                except Exception as e:
                    st.error(f"哎呀，网络出了点小差错。错误信息：{e}")

elif role == "👩‍🏫 教师端":
    st.title("📊 全班成绩汇总大屏 (教师端)")
    st.divider()
    
    # 教师端密码锁
    teacher_pwd = st.sidebar.text_input("请输入教师访问密码：", type="password", help="默认密码为：123456")
    
    if teacher_pwd == "123456":
        df = load_records()
        
        if len(df) > 0:
            # 顶部统计卡片
            col1, col2, col3 = st.columns(3)
            col1.metric("已交卷人数", f"{len(df)} 人")
            
            # 统计完全无错的人数
            correct_count = len(df[df['错误类型'] == '无错'])
            col2.metric("完全正确人数", f"{correct_count} 人")
            
            # 数据表展示
            st.subheader("📋 详细作答记录")
            st.dataframe(df, use_container_width=True)
            
            # 数据可视化
            st.subheader("📈 班级错误类型分布")
            error_counts = df['错误类型'].value_counts().reset_index()
            error_counts.columns = ['错误类型', '人数']
            
            chart = alt.Chart(error_counts).mark_bar().encode(
                x=alt.X('错误类型', title='', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('人数', title='人数', scale=alt.Scale(domainMin=0), axis=alt.Axis(tickMinStep=1)),
                color='错误类型'
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
            
        else:
            st.info("目前还没有学生交卷哦，稍后再来查看吧！")
    elif teacher_pwd != "":
        st.sidebar.error("密码错误，拒绝访问！")
