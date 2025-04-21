import streamlit as st
from io import BytesIO
from pdf2image import convert_from_bytes
import fitz 
import json, os, hashlib, base64
from extract import ExtractTextInfoFromPDF
from PIL import ImageDraw, ImageFont
from streamlit.components.v1 import html
from dotenv import load_dotenv
from openai import OpenAI


st.set_page_config(
    page_title="☁️ Confer · Research Companion",
    layout="wide",
    # initial_sidebar_state="collapsed"
)
st.markdown(
    "<h3 style='text-align:center;'>Confer · Your Research Companion</h3>",
    unsafe_allow_html=True
)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
st.session_state.setdefault("summaries", {})

with st.sidebar:
    st.header("User Settings")
    st.selectbox(
        "Select your proficiency level:",
        ["Beginner", "Medium", "Advanced"],
        index=1,
        key="user_level"
    )
    st.text_input(
        "Preferred teaching style:",
        value="",
        key="teaching_style"
    )
    # new_pdf = st.file_uploader("Select a PDF", type="pdf", key="sidebar_pdf")


def get_prompt_prefix():
    level = st.session_state.get("user_level", "Medium")
    style = st.session_state.get("teaching_style", "").strip()
    prefix = f"You are assisting a {level}‑level user."
    if style:
        prefix += f" Teaching style: {style}."
    return prefix


def summarize_text(text: str) -> str:
    """Ask ChatGPT to produce a concise summary using global context."""
    summary_context = st.session_state.get("global_summary", "")
    full_prompt = f"""You are a succinct summarizer. Here is the overall context of the document:{summary_context} Now, please summarize this specific section:{text}"""
    prefix = get_prompt_prefix()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
        { "role": "system",
            "content": f"{prefix} You are a helpful assistant for academic summarization."
        },
        { "role": "user",
            "content": f"{prefix}\nHere is the overall context: {summary_context}\nNow summarize:\n{text}" }
        ],
        temperature=0.3,
        max_tokens=200
    )
    return response.choices[0].message.content.strip()
      

def summarize_entire_pdf(elts) -> str:
    """Summarizes the entire PDF in chunks and then summarizes those summaries."""
    all_text = "\n".join(el.get("Text", "") for el in elts if "Text" in el).strip()
    if not all_text:
        return "No extractable text found in the PDF."

    chunks = chunk_text(all_text, max_chars=8000)
    print(f"Chunk count: {len(chunks)}")
    print(f"Chunk 0 length: {len(chunks[0])} characters")

    intermediate_summaries = []

    for i, chunk in enumerate(chunks):
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": f"Summarize this part of a research paper:\n\n{chunk}"}
            ],
            temperature=0.3,
            max_tokens=500
        )
        summary = response.choices[0].message.content.strip()
        intermediate_summaries.append(summary)

    combined_summary_text = "\n".join(intermediate_summaries)

    final_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that combines summaries into one final summary."},
            {"role": "user", "content": f"Combine and summarize the following summaries:\n\n{combined_summary_text}"}
        ],
        temperature=0.3,
        max_tokens=500
    )

    return final_response.choices[0].message.content.strip()

def chunk_text(text, max_chars):
    """Splits text into chunks of a specified maximum character length."""
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        if len(" ".join(current_chunk + [word])) > max_chars:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
        else:
            current_chunk.append(word)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def render_images(pdf):
    b = BytesIO(pdf.read())
    pages = convert_from_bytes(b.getvalue(), size=(612,792))
    pdf.seek(0)
    return pages

def page_sizes(pdf):
    pdf.seek(0)
    doc = fitz.open(stream=pdf.read(), filetype="pdf")
    return [(p.rect.width, p.rect.height) for p in doc]

def md5sum(pdf):
    pdf.seek(0)
    return hashlib.md5(pdf.read()).hexdigest()

def parse_pdf(pdf):
    h      = md5sum(pdf)
    outdir = f"output/ExtractTextInfoFromPDF/{h}"
    datafn = os.path.join(outdir, "structuredData.json")
    if not os.path.exists(datafn):
        os.makedirs(outdir, exist_ok=True)
        pdf.seek(0)
        with open("extractPdfInput.pdf","wb") as f:
            f.write(pdf.read())
        st.session_state["extracted_images"] = extract_images_from_pdf("uploaded.pdf")
        ExtractTextInfoFromPDF(output_path=datafn)
    return json.load(open(datafn)), outdir

 


def extract_images_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    image_info_list = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)

        for img_index, img in enumerate(images):
            xref = images[img_index][0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]

            image_info_list.append({
                "page": page_index,
                "image_bytes": image_bytes,
                "extension": ext,
                "xref": xref
            })

    return image_info_list


def nav(delta):
    st.session_state.current_page = max(
        0,
        min(st.session_state.current_page + delta, len(st.session_state.images) - 1)
    )
    st.session_state.active_idx = None
    st.rerun()

for k,v in {
    "pdf_uploaded": False,
    "images": [],
    "sizes": [],
    "parsed": {},
    "outdir": "",
    "current_page": 0,
    "active_idx": None
}.items():
    st.session_state.setdefault(k, v)


if not st.session_state.pdf_uploaded:
    st.header("Upload a PDF")
    up = st.file_uploader("Select a PDF", type="pdf")
    if up:
        st.session_state.pdf_uploaded = True
        st.session_state.images     = render_images(up)
        st.session_state.sizes      = page_sizes(up)
        st.session_state.parsed, st.session_state.outdir = parse_pdf(up)

        with st.spinner("Summarizing the entire PDF..."):
            st.session_state["global_summary"] = summarize_entire_pdf(st.session_state.parsed.get("elements", []))
        
        st.rerun()
    else:
        st.stop()


imgs = st.session_state.images
w_pts, h_pts = st.session_state.sizes[st.session_state.current_page]
elts = st.session_state.parsed.get("elements", [])



st.session_state.setdefault("per_el_state", {})  
def bucket(idx):
    return st.session_state.per_el_state.setdefault(idx, {"chat": "", "notes": ""})

page = st.session_state.current_page
active = st.session_state.active_idx



disp_w = 612
scale_x = disp_w / w_pts
scale_y = imgs[page].height / h_pts


def draw_boxes_on_image(image, elements, page_index, active_idx=None):
    draw = ImageDraw.Draw(image)

    if active_idx is not None:
        el = elements[active_idx]
        if el.get("Page") == page_index and "Bounds" in el:
            l, b, r, t = el["Bounds"]
            x0 = l * scale_x
            y0 = (h_pts - t) * scale_y
            x1 = r * scale_x
            y1 = (h_pts - b) * scale_y
            draw.rectangle([x0, y0, x1, y1], outline="gold", width=2)

    return image




buf = BytesIO()
imgs[page].save(buf, format="PNG")
img64 = base64.b64encode(buf.getvalue()).decode()

col1, col2 = st.columns([2,1])

with st.sidebar:
    st.header("Components")
    for i, el in enumerate(elts):
        if el.get("Page") != page or "Bounds" not in el:
            continue
        txt_preview = el.get("Text", "")[:100].strip() or "[no text]"
        if st.button(f"{i}: {txt_preview}", key=f"el_btn_{i}"):
            st.session_state.active_idx = i
            st.rerun()



with col1:

    buf = BytesIO()
    imgs[page].save(buf, format="PNG")
    img64 = base64.b64encode(buf.getvalue()).decode()

    highlight_boxes = []
    for i, el in enumerate(elts):
        if el.get("Page") != page or "Bounds" not in el:
            continue
        l, b, r, t = el["Bounds"]
        x = l * scale_x
        y = (h_pts - t) * scale_y
        w = (r - l) * scale_x
        h = (t - b) * scale_y

        border = "2px solid #FFD700" if i == active else "1px solid rgba(0,0,0,0.1)"
        background = "rgba(255,215,0,0.15)" if i == active else "transparent"

        highlight_boxes.append(f"""
        <div onclick="select({i})"
            style="position:absolute; left:{x}px; top:{y}px;
                    width:{w}px; height:{h}px;
                    border:{border}; background:{background};
                    cursor:pointer;">
        </div>
        """)

    html_code = f"""
    <div style="position:relative; width:{disp_w}px; height:{imgs[page].height}px;">
    <img src="data:image/png;base64,{img64}"
        style="width:{disp_w}px; height:{imgs[page].height}px; display:block;" />
    {''.join(highlight_boxes)}
    </div>
    <script>
    function select(idx) {{
        window.parent.postMessage({{
        isStreamlitMessage: true,
        type: "streamlit:setComponentValue",
        value: idx
        }}, "*");
    }}
    </script>
    """

    clicked = html(html_code, height=imgs[page].height + 30)
    if isinstance(clicked, (int, float)):
        st.session_state.active_idx = int(clicked)
        st.rerun()

    c1, c2 = st.columns([1,1])
    with c1:
        if st.button("⬅️ Prev"):
            nav(-1)
    with c2:
        if st.button("Next ➡️"):
            nav(+1)

    sel = st.selectbox(
        "Go to page:",
        list(range(len(imgs))),
        index=page,
        format_func=lambda i: f"Page {i+1}",
        key="page_sel"
    )
    if sel != page:
        st.session_state.current_page = sel
        st.session_state.active_idx = None
        st.rerun()

with col2:
    tab1, tab2, tab3 = st.tabs(["Summary", "Chat", "Notes"])

    el = None
    if st.session_state.active_idx is not None:
        idx = st.session_state.active_idx
        if 0 <= idx < len(elts):
            el = elts[idx]

    # Summary
    with tab1:
        st.subheader("Component Preview")
        if not el:
            st.info("Click an element on the left.")
        else:
            txt = el.get("Text", "").strip()
            if txt:
                st.code(txt, language="markdown")

                if st.button("Summarize this", key=f"summarize_{idx}"):
                    with st.spinner("Summarizing…"):
                        summary = summarize_text(txt)
                        st.session_state["summaries"][idx] = summary
                    st.rerun()

                summary = st.session_state["summaries"].get(idx)
                if summary:
                    st.markdown("**Summary:**")
                    st.markdown(summary)

            else:
                st.info("No text to summarize for this component.")

    # Chat
with tab2:
    st.subheader("Chat")
    if not el:
        st.info("Select an element first.")
    else:
        b = bucket(idx)
        text_context = el.get("Text", "").strip()
        q = st.text_input("Ask about this component:", key=f"chat_q_{idx}")
        if q:
            if st.button("Send", key=f"chat_send_{idx}"):
                with st.spinner("Thinking..."):
                    global_summary = st.session_state.get("global_summary", "")
                    prefix = get_prompt_prefix()
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                        { "role":"system",
                            "content": f"{prefix} You are a helpful assistant answering questions about research papers."
                        },
                        { "role":"user",
                            "content": f"{prefix}\nFull paper summary: {global_summary}\nSection text: {text_context}\nUser question: {q}" }
                        ],
                        temperature=0.4,
                        max_tokens=400
                    )
                    b["chat"] = q
                    b["chat_response"] = response.choices[0].message.content.strip()
                st.rerun()
        if b.get("chat_response"):
            st.markdown("**Response:**")
            st.markdown(b["chat_response"])



    # Notes
    with tab3:
        st.subheader("Your Notes")
        if not el:
            st.info("Select an element first.")
        else:
            b = bucket(idx)
            b["notes"] = st.text_area("Notes:",
                                      key=f"notes_{idx}",
                                      value=b["notes"],
                                      height=200)
            st.download_button(
                label="Download Notes",
                data=b["notes"],
                file_name=f"notes_component_{idx}.txt",
                mime="text/plain"
            )
