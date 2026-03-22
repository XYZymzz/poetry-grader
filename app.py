import time
import streamlit as st
import pandas as pd
import os
import json
import altair as alt
import base64
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
# 核心升级：读取本地图片并进行 Base64 注入
# ==========================================
def set_bg_from_local(image_file):
    if os.path.exists(image_file):
        with open(image_file, "rb") as f:
            data = f.read()
            
        b64_encoded = base64.b64encode(data).decode()
        
        page_bg_img = f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{b64_encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-color: rgba(255,255,255,0.6);
            background-blend-mode: overlay;
        }}
        </style>
        """
        st.markdown(page_bg_img, unsafe_allow_html=True)
    else:
        st.warning(f"⚠️ 系统提示：未能找到背景图片 '{image_file}'，请确认图片是否与 app.py 在同一目录下。")

set_bg_from_local("background.jpg")

# ==========================================
# 高阶应用：初始化全局状态机 (Session State)
# ==========================================
if "follow_up_active" not in st.session_state:
    st.session_state.follow_up_active = False  
if "last_q_id" not in st.session_state:
    st.session_state.last_q_id = None          
if "temp_name" not in st.session_state:
    st.session_state.temp_name = ""            
if "temp_id" not in st.session_state:
    st.session_state.temp_id = ""              
if "follow_up_q" not in st.session_state:
    st.session_state.follow_up_q = ""          
if "wrong_feedback" not in st.session_state:
    st.session_state.wrong_feedback = ""       

if "fu_completed" not in st.session_state:
    st.session_state.fu_completed = False      
if "fu_result_dict" not in st.session_state:
    st.session_state.fu_result_dict = {}       
if "fu_submitted_ans" not in st.session_state:
    st.session_state.fu_submitted_ans = ""     
if "orig_ans" not in st.session_state:
    st.session_state.orig_ans = ""

# ==========================================
# 数据持久化
# ==========================================
DATA_FILE = "class_records.csv"

def load_records():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["学号", "学生姓名", "题目", "学生作答", "判定状态", "错误类型", "AI 详细反馈"])

def save_record(new_record):
    df = load_records()
    new_df = pd.DataFrame([new_record])
    df = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)

# ==========================================
# 题库定义
# ==========================================
questions_db = {
    "理解性默写1": {
        "type": "fill",
        "question": "诗中哪一句以简练笔触勾勒出诗人奉命出使的场景，字里行间隐含漂泊无依的孤寂感，为全诗雄浑苍凉的边塞氛围铺垫？",
        "answer": "单车欲问边，属国过居延"
    },
    "理解性默写2": {
        "type": "fill",
        "question": "诗中哪一句的翻译为“像随风而去的蓬草一样出临边塞，北归大雁正翱翔云天”？",
        "answer": "征蓬出汉塞，归雁入胡天"
    },
    "理解性默写3": {
        "type": "fill",
        "question": "诗中哪一句虽为水墨意境，但通过“大漠”的黄、“孤烟”的黑、“落日”的红等色彩的暗示，营造出丰富而深沉的视觉效果？",
        "answer": "大漠孤烟直，长河落日圆"
    },
    "理解性默写4": {
        "type": "fill",
        "question": "诗中哪一句是诗人从候骑口中得到的最新军情，且暗含对战事顺利的期盼？",
        "answer": "萧关逢候骑，都护在燕然"
    },
    "诗词赏析题": {
        "type": "essay",
        "question": "颈联“大漠孤烟直，长河落日圆”被赞为“千古壮观”，请从炼字和画面意境两个角度赏析这句诗。",
        "answer": "1. 炼字角度：“直”字写出大漠中孤烟挺拔坚毅的姿态，无多余曲折，尽显大漠的雄浑辽阔；“圆”字描绘落日低垂、浑圆温暖的形态，柔和又壮阔。一“直”一“圆”，用词简洁精准，极简笔墨勾勒出边塞特有的景致。\n2. 意境角度：诗句描绘出浩瀚沙漠中孤烟笔直升起，奔流黄河上落日浑圆低垂的画面，意境雄浑苍凉、辽阔壮美，既写出边塞的荒凉孤寂，又展现出大漠的磅礴气势，情景交融。"
    },
    "情感分析题": {
        "type": "essay",
        "question": "结合全诗，分析诗人“单车欲问边”到观景后的情感变化。",
        "answer": "诗人开篇以“单车”“征蓬”“归雁”自比，轻车简从出使边塞，像飘飞的蓬草、北归的大雁般远离故土，流露出漂泊无依的孤寂、抑郁与飘零之感；行至边塞见到“大漠孤烟直，长河落日圆”的壮阔奇景后，被雄浑壮丽的边塞风光震撼，孤寂之情消散，转而生出对边塞风光的赞叹，心境转为开阔豁达，也暗含对边关雄浑气象的敬畏。"
    }
}

# ==========================================
# 提示词矩阵
# ==========================================
prompt_fill = """
你是一个专业严谨但态度极其温柔、懂得启发学生的语文老师。你的任务是批改学生关于王维《使至塞上》的理解性默写题。
【题目】：{q}
【标准答案】：{a}
【学生作答】：{s}

请按以下严谨的标准批改，并只输出 JSON 格式的数据：
1. 判定逻辑：与标准答案完全一致判定为 correct；有错别字判定为 typo；完全填错判定为 wrong。
⚠️ 核心指令（绝对不可违反）：如果判定为 wrong，你必须在 follow_up_q 字段中，专门针对上方的【标准答案】（即“{a}”）重新设计一道全新视角的情景默写题。这道新题的正确答案必须、绝对、只能是【标准答案】！严禁顺着学生写错的诗句去出题！
2. 语气约束：你的 feedback 必须使用温柔、鼓励的语气。答错要温柔安抚并耐心引导，严禁生硬指责。

你的 JSON 输出格式必须严格如下：
{{
  "status": "correct | typo | wrong",
  "feedback": "极其温柔、带有鼓励性质的反馈话语",
  "error_type": "无错 | 错别字 | 诗句填错",
  "follow_up_q": "如果是 wrong，这里填入专门针对【标准答案】设计的新题，否则为空字符串"
}}
"""

prompt_essay = """
你是一个专业严谨但态度极其温柔、充满鼓励的语文老师。你的任务是批改学生关于王维《使至塞上》的主观问答题。
【题目】：{q}
【标准答案】：{a}
【学生作答】：{s}

请按以下严谨的标准批改，并只输出 JSON 格式的数据：
1. 批改逻辑（必须严谨）：严格对比标准答案的采分点，准确指出学生遗漏的角度和需要提升的地方。
2. 语气约束（必须温柔）：像知心导师一样，先敏锐地放大夸奖学生的思考闪光点，再用非常温柔、有亲和力的语气给出修改建议。

你的 JSON 输出格式必须严格如下：
{{
  "status": "subjective",
  "feedback": "极其温柔、充满夸奖与鼓励的点评和详细建议",
  "error_type": "主观题"
}}
"""

prompt_follow_up = """
你是一个专业严谨但极其包容的语文老师。现在学生正在进行【错题巩固训练】。
【巩固题目】：{q}
【该诗句标准答案】：{a}
【学生作答】：{s}

请按以下严谨的标准批改，并只输出 JSON 格式的数据：
1. 批改逻辑（必须严谨）：明确且准确地告知学生这次写对了还是写错了，精准指出错在哪里。
2. 严禁行为：绝对禁止再出新的测试题！只需给出本次作答的点评。
3. 语气约束（必须温柔）：面对错题重练的学生，你的语气必须加倍温柔。答对给予高度认可；答错要极其温柔地安抚和解析。

你的 JSON 输出格式必须严格如下：
{{
  "status": "correct | typo | wrong",
  "feedback": "极其温柔且带有安抚性质的反馈话语（明确对错，指出细节，绝对不要包含新题目）",
  "error_type": "无错 | 错别字 | 诗句填错"
}}
"""

# ==========================================
# 侧边栏路由
# ==========================================
st.sidebar.title("⚙️ 系统控制台")
role = st.sidebar.radio("请选择登录身份：", ["👨‍🎓 学生端", "👩‍🏫 教师端"])

# ==========================================
# 业务逻辑视图
# ==========================================
if role == "👨‍🎓 学生端":
    st.title("📝 王维《使至塞上》智能批改系统")
    st.divider()

    selected_q_id = st.selectbox("请选择你要测试的题目：", list(questions_db.keys()))
    current_q_data = questions_db[selected_q_id]
    current_q_type = current_q_data["type"]
    current_q_text = current_q_data["question"]
    current_standard_answer = current_q_data["answer"]

    if st.session_state.last_q_id != selected_q_id:
        st.session_state.last_q_id = selected_q_id
        st.session_state.follow_up_active = False
        st.session_state.fu_completed = False
        st.session_state.fu_result_dict = {}
        st.session_state.fu_submitted_ans = ""
        st.session_state.orig_ans = ""

    # ---------------- 状态分离 A：正常作答模式 ----------------
    if not st.session_state.follow_up_active:
        st.markdown(f"### 📌 题目内容：")
        st.success(current_q_text)
        
        if current_q_type == "essay":
            st.caption("👇 这是一道主观题，请在下方尽情输入你的分析与见解")
        else:
            st.caption("👇 请仔细阅读上方提示，并在下方输入正确的诗句")

        with st.form(key="student_submit_form"):
            col1, col2 = st.columns(2)
            with col1:
                student_name = st.text_input("请输入姓名：", value=st.session_state.temp_name)
            with col2:
                student_id = st.text_input("请输入学号（8位纯数字）：", value=st.session_state.temp_id)
            
            if current_q_type == "essay":
                student_answer = st.text_area("请输入你的答案：", key=f"answer_{selected_q_id}", height=150)
            else:
                student_answer = st.text_input("请输入你的答案：", key=f"answer_{selected_q_id}")
            
            submitted = st.form_submit_button("🚀 提交并获取批改")

        if submitted:
            st.session_state.temp_name = student_name
            st.session_state.temp_id = student_id

            if student_answer.strip() == "" or student_name.strip() == "" or student_id.strip() == "":
                st.warning("⚠️ 学号、姓名和答案都不能为空哦！请重新填写。")
            elif not student_id.isdigit() or len(student_id) != 8:
                st.warning("🚨 学号格式错误！必须是刚好 8 位的纯数字。")
            else:
                active_prompt = prompt_essay if current_q_type == "essay" else prompt_fill
                final_prompt = active_prompt.format(q=current_q_text, a=current_standard_answer, s=student_answer)
                
                with st.spinner("AI 老师正在飞速批阅中，请稍候..."):
                    try:
                        response = client.chat.completions.create(
                            model="deepseek-chat", 
                            messages=[{"role": "user", "content": final_prompt}],
                            response_format={"type": "json_object"}, 
                            temperature=0.1 
                        )
                        ai_result_dict = json.loads(response.choices[0].message.content)
                        
                        new_record = {
                            "学号": student_id,
                            "学生姓名": student_name,
                            "题目": selected_q_id,
                            "学生作答": student_answer,
                            "判定状态": ai_result_dict.get("status"),
                            "错误类型": ai_result_dict.get("error_type"),
                            "AI 详细反馈": ai_result_dict.get("feedback")
                        }
                        save_record(new_record)

                        if current_q_type == "fill" and ai_result_dict.get("status") == "wrong":
                            st.session_state.follow_up_active = True
                            st.session_state.wrong_feedback = ai_result_dict.get("feedback")
                            st.session_state.follow_up_q = ai_result_dict.get("follow_up_q", f"请再次默写这句诗：{current_standard_answer}")
                            st.session_state.orig_ans = student_answer  
                            st.rerun()  
                        else:
                            st.success(f"批改完成！成绩已成功上传至教师端。")
                            st.write("✨ **AI 老师给你的专属反馈：**", ai_result_dict.get("feedback"))
                            if current_q_type == "essay":
                                st.info(f"📖 **标准答案参考：**\n\n{current_standard_answer}")
                        
                    except Exception as e:
                        st.error(f"网络异常：{e}")

    # ---------------- 状态分离 B：错题巩固模式 ----------------
    else:
        st.markdown(f"### 📌 原题内容：")
        st.success(current_q_text)
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.text_input("姓名：", value=st.session_state.temp_name, disabled=True)
        with col_info2:
            st.text_input("学号：", value=st.session_state.temp_id, disabled=True)

        st.text_input("📝 你在原题中的作答：", value=st.session_state.orig_ans, disabled=True)
        
        # ==============================================================
        # 核心修改点：将错误提示框和诊断报告移到用户原始输入数据的下方
        # ==============================================================
        st.error("❌ 哎呀，你刚才的作答有误，系统已为你开启【错题巩固模式】！")
        st.write("✨ **首次作答诊断：**", st.session_state.wrong_feedback)
        
        st.divider()
        st.markdown(f"### 🎯 巩固题靶向训练：")
        st.info(st.session_state.follow_up_q)

        if not st.session_state.fu_completed:
            with st.form(key="follow_up_form"):
                fu_answer = st.text_input("请输入巩固题的答案：")
                fu_submitted = st.form_submit_button("🚀 提交巩固作答")

            if fu_submitted:
                if fu_answer.strip() == "":
                    st.warning("巩固题答案不能为空！")
                else:
                    st.session_state.fu_submitted_ans = fu_answer
                    final_prompt = prompt_follow_up.format(q=st.session_state.follow_up_q, a=current_standard_answer, s=fu_answer)
                    
                    with st.spinner("AI 老师正在认真审阅你的巩固答案..."):
                        try:
                            response = client.chat.completions.create(
                                model="deepseek-chat", 
                                messages=[{"role": "user", "content": final_prompt}],
                                response_format={"type": "json_object"}, 
                                temperature=0.1 
                            )
                            fu_ai_result = json.loads(response.choices[0].message.content)
                            
                            fu_record = {
                                "学号": st.session_state.temp_id,
                                "学生姓名": st.session_state.temp_name,
                                "题目": selected_q_id + " (二次巩固)",
                                "学生作答": fu_answer,
                                "判定状态": fu_ai_result.get("status"),
                                "错误类型": fu_ai_result.get("error_type"),
                                "AI 详细反馈": fu_ai_result.get("feedback")
                            }
                            save_record(fu_record)
                            
                            st.session_state.fu_result_dict = fu_ai_result
                            st.session_state.fu_completed = True
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"网络异常：{e}")
        else:
            st.text_input("📝 你在巩固题中的作答：", value=st.session_state.fu_submitted_ans, disabled=True)
            
            res = st.session_state.fu_result_dict
            if res.get("status") == "correct":
                st.success("🎉 太棒了！巩固题回答完全正确，看来你已经掌握了！")
            elif res.get("status") == "typo":
                st.warning("👀 哎呀，还是有点小瑕疵（写了错别字），下次一定要注意细节哦。")
            else:
                st.error("❌ 还是不对哦，请仔细查看老师的最终解析，课后记得多加复习。")
            
            st.write("✨ **AI 老师对巩固题的点评：**", res.get("feedback"))
            
            if st.button("🔙 结束本次巩固，返回原题模式", type="primary"):
                st.session_state.follow_up_active = False
                st.session_state.fu_completed = False
                st.session_state.fu_result_dict = {}
                st.session_state.fu_submitted_ans = ""  
                st.session_state.orig_ans = ""
                st.rerun()

elif role == "👩‍🏫 教师端":
    st.title("📊 班级学情汇总大屏 (教师端)")
    st.divider()
    
    teacher_pwd = st.sidebar.text_input("请输入教师访问密码：", type="password", help="默认密码为：123456")
    
    if teacher_pwd == "123456":
        df = load_records()
        
        if len(df) > 0:
            df_fill = df[df['错误类型'] != '主观题']
            df_essay = df[df['错误类型'] == '主观题']
            
            st.subheader("🎯 第一部分：理解性默写统计 (包含巩固数据)")
            if len(df_fill) > 0:
                col1, col2 = st.columns(2)
                col1.metric("默写总提交人次", f"{len(df_fill)} 人次")
                correct_count = len(df_fill[df_fill['错误类型'] == '无错'])
                col2.metric("完全正确人次", f"{correct_count} 人次")
                
                error_counts = df_fill['错误类型'].value_counts().reset_index()
                error_counts.columns = ['错误类型', '人次']
                
                chart = alt.Chart(error_counts).mark_bar().encode(
                    x=alt.X('错误类型', title='', axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('人次', title='人次', scale=alt.Scale(domainMin=0), axis=alt.Axis(tickMinStep=1)),
                    color='错误类型'
                ).properties(height=250)
                st.altair_chart(chart, use_container_width=True)
                
                with st.expander("查看默写题详细作答记录 (带有'二次巩固'字样为追问题)"):
                    st.dataframe(df_fill, use_container_width=True)
            else:
                st.info("暂无理解性默写的作答数据。")
                
            st.divider()
            
            st.subheader("✍️ 第二部分：主观题作答追踪")
            if len(df_essay) > 0:
                st.dataframe(df_essay[['学号', '学生姓名', '题目', '学生作答']], use_container_width=True)
                with st.expander("查看主观题 AI 点评记录"):
                    st.dataframe(df_essay[['学号', '学生姓名', '题目', 'AI 详细反馈']], use_container_width=True)
            else:
                st.info("暂无主观题的作答数据。")
                
            st.divider()
            if st.button("🗑️ 清空所有学生数据", type="primary", use_container_width=True):
                if os.path.exists(DATA_FILE):
                    os.remove(DATA_FILE)
                st.success("✅ 数据已成功清空！界面即将刷新...")
                time.sleep(1)
                st.rerun()
        else:
            st.info("目前还没有学生交卷哦，稍后再来查看吧！")
    elif teacher_pwd != "":
        st.sidebar.error("密码错误，拒绝访问！")
