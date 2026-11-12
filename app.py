"""WasteOps public product experience.

The legacy Streamlit CSV dashboard has been retired. Live operational work belongs
in the authenticated API-backed operator console (web/index.html). This page is
a branded product entry point and intentionally never fabricates operational data.
"""
import os

import streamlit as st

st.set_page_config(
    page_title="WasteOps | Smart Collection Operations",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CONSOLE_URL = os.getenv("WASTEOPS_CONSOLE_URL", "https://wasteops-production.onrender.com").strip()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root { color-scheme: dark; }
    .stApp {
      background:
        radial-gradient(ellipse at 8% 0%, rgba(38,112,91,.24), transparent 34%),
        radial-gradient(ellipse at 92% 12%, rgba(58,105,137,.18), transparent 30%),
        #081411;
      color: #edf7f1;
      font-family: 'DM Sans', sans-serif;
    }
    [data-testid="stHeader"] { background: rgba(8,20,17,.72); }
    [data-testid="stToolbar"], #MainMenu, footer { visibility: hidden; }
    .block-container { max-width: 1180px; padding-top: 2.1rem; padding-bottom: 4rem; }
    .brandbar { display:flex; align-items:center; justify-content:space-between; gap:16px;
      padding: 8px 0 26px; border-bottom:1px solid rgba(194,225,207,.13); }
    .brand { display:flex; align-items:center; gap:12px; }
    .brandmark { width:44px; height:44px; display:grid; place-items:center; border-radius:14px;
      color:#071b13; font-size:24px; background:linear-gradient(145deg,#a8e6c1,#58c89a);
      box-shadow:0 8px 28px rgba(73,196,141,.16); }
    .brandname { color:#f2fbf5; font:800 20px 'Manrope',sans-serif; letter-spacing:-.7px; }
    .brandmeta { color:#8ca99a; font-size:11px; letter-spacing:2px; text-transform:uppercase; }
    .topnote { color:#a5c3b2; font-size:12px; border:1px solid rgba(153,205,174,.22);
      border-radius:999px; padding:8px 12px; background:rgba(20,55,41,.42); }
    .hero { padding: clamp(42px,8vw,92px) 0 42px; max-width:900px; }
    .eyebrow { color:#8fe0b2; text-transform:uppercase; letter-spacing:2.6px; font-size:11px;
      font-weight:700; margin-bottom:18px; }
    .hero h1 { color:#f3faf5; font:800 clamp(42px,7vw,76px)/1.04 'Manrope',sans-serif;
      letter-spacing:-3.5px; margin:0 0 22px; }
    .hero p { color:#a9c2b4; font-size:clamp(16px,2vw,19px); line-height:1.75;
      max-width:720px; margin:0; }
    .hero-accent { color:#91e0b3; }
    .section-label { color:#8fe0b2; text-transform:uppercase; letter-spacing:2px;
      font-size:11px; font-weight:700; margin:28px 0 14px; }
    .feature { height:100%; min-height:190px; border:1px solid rgba(169,210,185,.15);
      border-radius:18px; padding:22px; background:linear-gradient(145deg,rgba(22,48,37,.86),rgba(13,31,25,.86));
      box-shadow:0 18px 45px rgba(0,0,0,.12); }
    .feature-icon { font-size:23px; margin-bottom:18px; }
    .feature h3 { color:#f0faf3; font:700 17px 'Manrope',sans-serif; margin:0 0 8px; }
    .feature p { color:#9db7a7; font-size:13px; line-height:1.65; margin:0; }
    .workflow { border:1px solid rgba(169,210,185,.15); background:rgba(13,31,25,.72);
      border-radius:18px; padding:22px 24px; margin-top:22px; }
    .step { color:#e8f5ec; font-weight:700; font-size:14px; }
    .step small { display:block; color:#91aa9b; font-weight:400; font-size:12px; margin-top:4px; }
    .stepnum { color:#8fe0b2; font:800 12px 'Manrope',sans-serif; letter-spacing:1px; }
    .trust { color:#87a393; font-size:12px; line-height:1.7; margin-top:24px; }
    .footerline { border-top:1px solid rgba(194,225,207,.13); margin-top:54px; padding-top:18px;
      color:#718d7e; font-size:11px; display:flex; justify-content:space-between; gap:12px; }
    div.stButton > button, div.stLinkButton > a {
      border:0; border-radius:11px; background:#8fe0b2; color:#082016; font-weight:800;
      padding: .72rem 1.2rem; min-height:46px; box-shadow:0 10px 28px rgba(85,194,137,.14);
    }
    div.stButton > button:hover, div.stLinkButton > a:hover { background:#b0edc9; color:#082016; }
    a { color:#9ce7bc !important; }
    @media(max-width:650px) {
      .brandbar { align-items:flex-start; flex-direction:column; }
      .hero h1 { letter-spacing:-2px; }
      .footerline { flex-direction:column; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="brandbar">
      <div class="brand">
        <div class="brandmark">♻</div>
        <div><div class="brandname">WasteOps</div><div class="brandmeta">Collection intelligence</div></div>
      </div>
      <div class="topnote">Smarter routes · Cleaner communities</div>
    </div>
    <section class="hero">
      <div class="eyebrow">A better way to manage urban waste</div>
      <h1>Cleaner streets start with <span class="hero-accent">smarter collection.</span></h1>
      <p>One connected workspace for waste monitoring, collection planning and field operations.
      Turn verified bin activity into clear priorities, efficient routes and accountable service.</p>
    </section>
    <div class="section-label">One connected operations workflow</div>
    """,
    unsafe_allow_html=True,
)

features = [
    ("◉", "Monitor collection points", "Bring registered bins and incoming sensor readings into one operational view. Review recent activity and spot service needs."),
    ("⌁", "Prioritise with context", "Combine observed fill levels, bin criticality and service history to help teams decide what needs attention first."),
    ("↗", "Plan practical routes", "Build vehicle-capacity-aware collection plans using road-network travel costs and route geometry."),
    ("✓", "Close the service loop", "Assign work to drivers, record collection outcomes and keep a traceable history of field actions."),
]
cols = st.columns(4, gap="medium")
for col, (symbol, title, description) in zip(cols, features):
    with col:
        st.markdown(
            f'<div class="feature"><div class="feature-icon">{symbol}</div>'
            f'<h3>{title}</h3><p>{description}</p></div>',
            unsafe_allow_html=True,
        )

st.markdown(
    """
    <div class="workflow">
      <div class="section-label" style="margin-top:0">From observation to verified collection</div>
    """,
    unsafe_allow_html=True,
)
steps = [
    ("01", "Observe", "Receive and review bin telemetry"),
    ("02", "Prioritise", "Identify service needs"),
    ("03", "Optimise", "Allocate work across vehicles"),
    ("04", "Collect", "Record driver actions and outcomes"),
]
step_cols = st.columns(4, gap="medium")
for col, (number, title, detail) in zip(step_cols, steps):
    with col:
        st.markdown(
            f'<div class="stepnum">{number}</div><div class="step">{title}<small>{detail}</small></div>',
            unsafe_allow_html=True,
        )
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="section-label">Access the platform</div>', unsafe_allow_html=True)
if CONSOLE_URL:
    st.link_button("Open WasteOps operator console ↗", CONSOLE_URL, use_container_width=False)
else:
    st.markdown(
        """
        <div class="workflow">
          <div class="step">Your collection operations, in one workspace.</div>
          <div class="trust">Sign in with your organization's WasteOps account to manage collection points,
          coordinate assignments and keep field teams aligned.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div class="trust">One workspace for collection monitoring, route planning and accountable field execution.</div>
    <div class="footerline"><span>WASTEOPS · SMART COLLECTION OPERATIONS</span><span>Built for accountable, data-informed services</span></div>
    """,
    unsafe_allow_html=True,
)
