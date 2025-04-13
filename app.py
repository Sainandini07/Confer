import streamlit as st
from pdf2image import convert_from_bytes
from io import BytesIO
import openai
import time


st.set_page_config(page_title="Confer - Research Simplified", layout="wide")
st.markdown("<h1 style='text-align: center;'>☁️ Confer: Your Research Companion</h1>", unsafe_allow_html=True)


def render_pdf_as_images(pdf_file):
    """Converts the uploaded PDF to images for page previews."""
    try:
        pdf_bytes = BytesIO(pdf_file.read())
        images = convert_from_bytes(pdf_bytes.getvalue())
        return images
    except Exception as e:
        st.error(f"Error processing PDF: {e}")
        return []

def generate_summary(text):
    """Generates a summary based on the user's input text."""
    prompt = f"Summarize the following text in simple terms:\n{text[:2000]}"
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def update_page(direction):
    if direction == -1 and st.session_state.current_page > 0:
        st.session_state.current_page -= 1
    elif direction == 1 and st.session_state.current_page < len(st.session_state.images) - 1:
        st.session_state.current_page += 1
    st.rerun()


defaults = {
    "expertise": "Student",
    "ease": "Easy",
    "roleplay": "Teach me like I'm 15",
    "pdf_uploaded": False,
    "uploaded_pdf": None,
    "pages": [],
    "images": [],
    "current_page": 0
}
for key, default in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Page 1 
if not st.session_state.pdf_uploaded:
    st.markdown("<h2 style='text-align: center;'>📤 Upload Your Research Paper</h2>", unsafe_allow_html=True)

    st.session_state.expertise = st.selectbox("📘 Select your expertise:", ["Student", "Beginner", "Researcher", "PhD", "Professor"])
    st.session_state.ease = st.radio("🧠 Preferred Explanation Level:", ["Easy", "Medium", "Hard"])
    st.session_state.roleplay = st.text_input("🎭 Roleplay Prompt (e.g. 'Teach me like I'm 15')")

    uploaded_pdf = st.file_uploader("📄 Upload your PDF file", type="pdf")

    if uploaded_pdf:
        st.session_state.pdf_uploaded = True
        st.session_state.uploaded_pdf = uploaded_pdf
        st.success("✅ PDF uploaded successfully! Generating interface...")
        time.sleep(1)
        st.rerun()

# Page 2
if st.session_state.pdf_uploaded and not st.session_state.images:
    with st.spinner("⏳ Converting PDF to images..."):
        st.session_state.images = render_pdf_as_images(st.session_state.uploaded_pdf)
        st.session_state.pages = ["Sample page 1 content.", "Sample page 2 content."]  
        st.session_state.current_page = 0
        st.rerun()


if st.session_state.images:
    
    col1, col2 = st.columns([2, 1])

   
    with col1:
        st.image(
            st.session_state.images[st.session_state.current_page],
            caption=f"Page {st.session_state.current_page + 1}",
            use_container_width=True  
        )

        
        nav1, nav2, nav3 = st.columns([5, 1, 1])
        with nav2:
            st.button("⬅️", on_click=lambda: update_page(-1), key="prev_btn")
        with nav3:
            st.button("➡️", on_click=lambda: update_page(1), key="next_btn")

        st.selectbox(
            "📑 Go to page:",
            [f"Page {i + 1}" for i in range(len(st.session_state.images))],
            index=st.session_state.current_page,
            on_change=lambda: st.rerun(),
            key="page_selector"
        )

   
    with col2:
        tab1, tab2, tab3 = st.tabs(["📄 Summary", "💬 Chat", "📝 Notes"])

        with tab1:
            st.subheader("Paper Summary")
            if st.button("Generate Summary"):
                summary = generate_summary(st.session_state.pages[st.session_state.current_page])
                st.write(summary)

        with tab2:
            st.subheader("Ask a Question About the Paper")
            user_question = st.text_input("Ask anything:")
            if user_question:
                st.write(f"Answer to: **{user_question}** (mock response)")

        with tab3:
            st.subheader("Your Notes")
            st.text_area("Write your thoughts here:", key="notepad", height=300)
