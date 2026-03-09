import streamlit as st
import pandas as pd
import os
import json
import altair as alt  # 新增：用来画更精细的图表，限制负数坐标轴
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
# 准备一个“记事本”，用来长期保存所有学生的成绩
# ==========================================
if "student_records" not in st.session_state:
    st.session_state.student_records = []

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
# 网页界面搭建
# ==========================================
st.title("📝 王安石《梅花》自动批改系统")
# （已将原文中的古诗 markdown 引用块删除）
st.divider()

st.subheader("👨‍🎓 学生答题区")

# 1. 选择题目
selected_q_id = st.selectbox("请选择你要测试的题目：", list(questions_db.keys()))
current_q_text = questions_db[selected_q_id]["question"]
current_standard_answer = questions_db[selected_q_id]["answer"]

# ==========================================
# 题目的精装修展示区
# ==========================================
st.markdown(f"### 📌 {selected_q_id} 题目内容：")
st.success(current_q_text)
st.caption("👇 请仔细阅读上方题目，并在下方输入你的答案")
# ==========================================

# 2. 收集学生作答
student_name = st.text_input("请输入学生姓名：", placeholder="例如：张三")
student_answer = st.text_input("请输入你的答案：", placeholder="输入诗句...")

# 3. 提交与大模型批改逻辑
if st.button("🚀 提交并批改"):
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
                
                # 获取 AI 结果并解析
                ai_result_str = response.choices[0].message.content
                ai_result_dict = json.loads(ai_result_str)
                
                st.success(f"批改完成！{student_name} 的答案已记录。")
                st.write("✨ **AI 反馈：**", ai_result_dict.get("feedback"))
                
                # 把这次的批改结果存进“记事本”里
                new_record = {
                    "学生姓名": student_name,
                    "题目": selected_q_id,
                    "学生作答": student_answer,
                    "判定状态": ai_result_dict.get("status"),
                    "错误类型": ai_result_dict.get("error_type"),
                    "AI 详细反馈": ai_result_dict.get("feedback")
                }
                st.session_state.student_records.append(new_record)
                
            except Exception as e:
                st.error(f"哎呀，调用大模型失败了。错误信息：{e}")

# ==========================================
# 最终阶段：数据统计与表格展示
# ==========================================
st.divider()
st.subheader("📊 班级成绩汇总表")

if len(st.session_state.student_records) > 0:
    df = pd.DataFrame(st.session_state.student_records)
    st.dataframe(df, use_container_width=True)
    
    st.write("📈 **班级错误类型分布：**")
    
    # 核心修改：使用 altair 画图，强制 Y 轴从 0 开始，且只显示整数
    error_counts = df['错误类型'].value_counts().reset_index()
    error_counts.columns = ['错误类型', '人数']
    
    chart = alt.Chart(error_counts).mark_bar().encode(
        x=alt.X('错误类型', title='', axis=alt.Axis(labelAngle=0)), # 名字横着显示，不倾斜
        y=alt.Y('人数', title='人数', scale=alt.Scale(domainMin=0), axis=alt.Axis(tickMinStep=1)) # 最小值为0，步长为1
    ).properties(height=300)
    
    st.altair_chart(chart, use_container_width=True)
    
else:
    st.info("目前还没有学生提交答案哦，快去上面模拟几个学生测试一下吧！")