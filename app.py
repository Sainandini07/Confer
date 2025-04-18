import streamlit as st
from io import BytesIO
from pdf2image import convert_from_bytes
import fitz 
import json, os, hashlib, base64
from extract import ExtractTextInfoFromPDF

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
        ExtractTextInfoFromPDF(output_path=datafn)
    return json.load(open(datafn)), outdir

def nav(delta):
    st.session_state.current_page = max(
        0,
        min(st.session_state.current_page + delta, len(st.session_state.images) - 1)
    )
    st.session_state.active_idx = None
    st.rerun()

st.set_page_config("☁️ Confer · Research Companion", layout="wide")
st.markdown(
    "<h1 style='text-align:center;'>☁️ Confer · Your Research Companion</h1>",
    unsafe_allow_html=True
)
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
    st.header("📤 Upload a PDF")
    up = st.file_uploader("📄 Select a PDF", type="pdf")
    if up:
        st.session_state.pdf_uploaded = True
        st.session_state.images     = render_images(up)
        st.session_state.sizes      = page_sizes(up)
        st.session_state.parsed, st.session_state.outdir = parse_pdf(up)
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

btns_html = []
for i, el in enumerate(elts):
    if el.get("Page") != page or "Bounds" not in el:
        continue
    l,b,r,t = el["Bounds"]
    x = l*scale_x
    y = (h_pts - t)*scale_y
    w = (r-l)*scale_x
    h = (t-b)*scale_y
    base = ("green" if "/Figure" in el["Path"]
            else "blue" if "/Table" in el["Path"]
            else "red")
    sel_border = "#FFD700" if active==i else "transparent"
    sel_bg     = "rgba(255,215,0,0.15)" if active==i else "transparent"

    btns_html.append(f'''
      <button id="el{i}"
        style="
          position:absolute;
          left:{x}px; top:{y}px;
          width:{w}px;  height:{h}px;
          background:{sel_bg};
          border:2px solid {sel_border};
          cursor:pointer; padding:0;
        "
        onmouseover="this.style.borderColor='{base}'"
        onmouseout="
          this.style.borderColor='{sel_border}';
          this.style.background='{sel_bg}';
        "
      ></button>
    ''')


buf = BytesIO()
imgs[page].save(buf, format="PNG")
img64 = base64.b64encode(buf.getvalue()).decode()





col1, col2 = st.columns([2,1])

with col1:
    st.image(imgs[page], use_container_width=True)
    for i, el in enumerate(elts):
        if el.get("Page") != page or "Bounds" not in el:
            continue

        txt_preview = el.get("Text", "")[:100].strip()
        if not txt_preview:
            txt_preview = "[no text]"

        if st.button(f"📍 Element {i}: {txt_preview}", key=f"el_btn_{i}"):
            st.session_state.active_idx = i
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
    tab1, tab2, tab3 = st.tabs(["📄 Summary", "💬 Chat", "📝 Notes"])

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
            else:
                fps = el.get("filePaths", [])
                if fps:
                    p = os.path.join(st.session_state.outdir, fps[0])
                    if os.path.exists(p):
                        st.image(p, use_column_width=True)
                    else:
                        st.warning("No image rendition found.")
                else:
                    st.info("No text or image for this element.")

    # Chat
    with tab2:
        st.subheader("Chaat")
        if not el:
            st.info("Select an element first.")
        else:
            b = bucket(idx)
            q = st.text_input("Ask about it:",
                              key=f"chat_q_{idx}",
                              value=b["chat"])
            b["chat"] = q

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
