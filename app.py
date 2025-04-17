import streamlit as st
from io import BytesIO
from pdf2image import convert_from_bytes
import json
import openai
import os
import hashlib
import fitz  # PyMuPDF
from extract import ExtractTextInfoFromPDF
from streamlit.components.v1 import html
import base64
from streamlit_js_eval import streamlit_js_eval
from collections import defaultdict

st.set_page_config(page_title="Confer - Research Simplified", layout="wide")
st.markdown("<h1 style='text-align: center;'>☁️ Confer: Your Research Companion</h1>", unsafe_allow_html=True)

def render_pdf_as_images(pdf_file):
    pdf_bytes = BytesIO(pdf_file.read())
    images = convert_from_bytes(pdf_bytes.getvalue(), size=(612, 792))
    pdf_file.seek(0)
    return images

def extract_page_dimensions(pdf_file):
    pdf_file.seek(0)
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    dimensions = []
    for page in doc:
        rect = page.rect
        dimensions.append((rect.width, rect.height))
    return dimensions

def get_pdf_hash(pdf_file):
    pdf_file.seek(0)
    return hashlib.md5(pdf_file.read()).hexdigest()

def load_or_parse_pdf(pdf_file):
    pdf_hash = get_pdf_hash(pdf_file)
    output_dir = f"output/ExtractTextInfoFromPDF/{pdf_hash}"
    json_path = os.path.join(output_dir, "structuredData.json")

    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            return json.load(f), output_dir
    else:
        os.makedirs(output_dir, exist_ok=True)
        pdf_file.seek(0)
        with open("extractPdfInput.pdf", "wb") as f:
            f.write(pdf_file.read())
        ExtractTextInfoFromPDF(output_path=json_path)
        with open(json_path, 'r') as f:
            return json.load(f), output_dir

def update_page(direction):
    if direction == -1 and st.session_state.current_page > 0:
        st.session_state.current_page -= 1
    elif direction == 1 and st.session_state.current_page < len(st.session_state.images) - 1:
        st.session_state.current_page += 1
    st.rerun()

def generate_summary(text):
    prompt = f"Summarize the following text in simple terms:\n{text[:2000]}"
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Session Defaults
defaults = {
    "pdf_uploaded": False,
    "uploaded_pdf": None,
    "parsed_data": {},
    "images": [],
    "page_dimensions": [],
    "current_page": 0,
    "clicked_element": None,
    "output_dir": "",
    "context_text": "",
    "context_type": ""
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Upload Section
if not st.session_state.pdf_uploaded:
    st.markdown("<h2 style='text-align: center;'>📤 Upload Your Research Paper</h2>", unsafe_allow_html=True)
    uploaded_pdf = st.file_uploader("📄 Upload your PDF file", type="pdf")

    if uploaded_pdf:
        st.session_state.pdf_uploaded = True
        st.session_state.uploaded_pdf = uploaded_pdf
        st.session_state.images = render_pdf_as_images(uploaded_pdf)
        st.session_state.page_dimensions = extract_page_dimensions(uploaded_pdf)
        parsed, output_dir = load_or_parse_pdf(uploaded_pdf)
        st.session_state.parsed_data = parsed
        st.session_state.output_dir = output_dir
        st.rerun()

# Display Page
if st.session_state.images:
    data = st.session_state.parsed_data
    elements = data.get("elements", [])
    page_num = st.session_state.current_page
    img = st.session_state.images[page_num]

    img_buf = BytesIO()
    img.save(img_buf, format="PNG")
    img_b64 = base64.b64encode(img_buf.getvalue()).decode()

    width_pts, height_pts = st.session_state.page_dimensions[page_num]
    display_width = 612
    scale_x = display_width / width_pts
    scale_y = img.height / height_pts
    scaled_height = img.height

    boxes_html = ""
    for i, el in enumerate(elements):
        if el.get("Page") != page_num or "Bounds" not in el:
            continue
        bounds = el["Bounds"]
        left, bottom, right, top = bounds
        x = left * scale_x
        y = (height_pts - top) * scale_y
        w = (right - left) * scale_x
        h = (top - bottom) * scale_y

        path = el.get("Path", "")
        if "/Figure" in path:
            color = "green"
        elif "/Table" in path:
            color = "blue"
        else:
            color = "red"

        boxes_html += f"""
        <button onclick=\"window.lastClickedBoxIndex = {i}\" style="
            position:absolute;
            left:{x}px;
            top:{y}px;
            width:{w}px;
            height:{h}px;
            background-color:transparent;
            border:2px solid transparent;
            cursor:pointer;
            padding:0;
        " onmouseover=\"this.style.borderColor='{color}';this.style.backgroundColor='rgba(255,0,0,0.05)'\"
          onmouseout=\"this.style.borderColor='transparent';this.style.backgroundColor='transparent'\"></button>
        """

    html_block = f"""
    <div style='position:relative;width:{display_width}px;height:{scaled_height}px;'>
        <img src="data:image/png;base64,{img_b64}" style="width:{display_width}px;height:{scaled_height}px;border:1px solid #ccc;">
        {boxes_html}
    </div>
    <script>window.lastClickedBoxIndex = null;</script>
    """

    col1, col2 = st.columns([2, 1])
    with col1:
        html(html_block, height=scaled_height + 30)
        selected_index = streamlit_js_eval(js_expressions="window.lastClickedBoxIndex", key="select-idx")

        nav1, nav2, nav3 = st.columns([5, 1, 1])
        with nav2:
            st.button("⬅️", on_click=lambda: update_page(-1), key="prev_btn")
        with nav3:
            st.button("➡️", on_click=lambda: update_page(1), key="next_btn")

        # st.selectbox(
        #     "📑 Go to page:",
        #     [f"Page {i + 1}" for i in range(len(st.session_state.images))],
        #     index=st.session_state.current_page,
        #     on_change=lambda: st.rerun(),
        #     key="page_selector"
        # )
        selected_page = st.selectbox(
        "📑 Go to page:",
        [f"Page {i + 1}" for i in range(len(st.session_state.images))],
        index=st.session_state.current_page,
        key="page_selector"
       )

    # Only rerun if the page number actually changes
    page_number = int(selected_page.split(" ")[1]) - 1
    if page_number != st.session_state.current_page:
        st.session_state.current_page = page_number
        st.experimental_rerun()

    with col2:
        tab1, tab2, tab3 = st.tabs(["📄 Summary", "💬 Chat", "📝 Notes"])
        if selected_index is not None and isinstance(selected_index, int):
            try:
                el = elements[selected_index]
                st.session_state.clicked_element = el
                st.session_state.context_text = el.get("Text", "")
                st.session_state.context_type = "text"
                if not st.session_state.context_text:
                    if "/Table" in el.get("Path", ""):
                        st.session_state.context_text = "[TABLE]"
                        st.session_state.context_type = "table"
                    elif "/Figure" in el.get("Path", ""):
                        st.session_state.context_text = "[FIGURE]"
                        st.session_state.context_type = "figure"
            except IndexError:
                st.warning("Invalid component selected.")
        


        context = st.session_state.get("context_text", "")
        context_type = st.session_state.get("context_type", "")
        selected = st.session_state.get("clicked_element")

        with tab1:
            st.subheader("Component Summary")
            if context:
                if st.button("Summarize this component") and context_type == "text":
                    st.write(generate_summary(context))
                elif context_type in ["table", "figure"] and selected and "filePaths" in selected:
                    img_path = os.path.join(st.session_state.output_dir, selected["filePaths"][0])
                    if os.path.exists(img_path):
                        st.image(img_path, use_column_width=True)
                    else:
                        st.warning("Image not found.")
                else:
                    st.info("No content to summarize.")
            else:
                st.info("Click on a component to summarize.")

        with tab2:
            st.subheader("Ask about selected component")
            if context:
                user_question = st.text_input("Ask anything:")
                if user_question:
                    st.write(f"Answer to: **{user_question}** using context: {context[:100]}...")
            else:
                st.info("Click on a component to chat about it.")

        with tab3:
            st.subheader("Your Notes")
            if context:
                st.text_area("Write notes for this section:", key="notepad", height=300)
            else:
                st.info("Click on a component to take notes.")
