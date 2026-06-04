/* ══════════════════════════════════════════════════════════════════
   ARIA · sample data
   Replace LEADS / CONVERSATIONS / DRAFTS with real fetch() calls
   when the API ships. Avatars come from Dicebear (no key required).
   ══════════════════════════════════════════════════════════════════ */

function avatar(seed, style = 'notionists') {
  const bg = ['c4b5fd','a5f3fc','fbcfe8','fde68a','bbf7d0','fed7aa','ddd6fe','fda4af'].join(',');
  return `https://api.dicebear.com/7.x/${style}/svg?seed=${encodeURIComponent(seed)}&backgroundColor=${bg}`;
}

const ME = {
  name:   'Arnav',
  email:  'arnavkumar9372@gmail.com',
  avatar: avatar('Arnav', 'avataaars'),
};

const LEADS = [
  // ── HOT (10) ──────────────────────────────────────────────────
  { id:1,  name:"Rajesh Kumar",    company:"AssuredMax Brokers",    handle:"@assuredmax",      role:"CEO",  lead_type:"broker",     channel:"facebook",  score:88, quality:"hot",  status:"demo_scheduled", intent:"demo_request",      team_size:15, pipeline:185000, created_at:"2026-05-03", city:"Mumbai" },
  { id:2,  name:"Priya Sharma",    company:"ShieldFirst IMF",       handle:"@shieldfirst",     role:"Founder", lead_type:"IMF",   channel:"instagram", score:79, quality:"hot",  status:"demo_done",      intent:"demo_request",      team_size:8,  pipeline:96000,  created_at:"2026-05-02", city:"Delhi" },
  { id:3,  name:"Amit Verma",      company:"TrustBond Brokers",     handle:"@trustbond",       role:"Director", lead_type:"broker",channel:"facebook",  score:92, quality:"hot",  status:"converted",      intent:"demo_request",      team_size:22, pipeline:264000, created_at:"2026-05-01", city:"Bangalore" },
  { id:4,  name:"Sunita Patel",    company:"ProtectPlus Agency",    handle:"@protectplus",     role:"Owner", lead_type:"corporate",channel:"facebook",  score:75, quality:"hot",  status:"needs_call",     intent:"pricing_query",     team_size:5,  pipeline:60000,  created_at:"2026-05-06", city:"Ahmedabad" },
  { id:5,  name:"Vikram Mehta",    company:"InsureMax Brokers",     handle:"@insuremax",       role:"MD", lead_type:"broker",     channel:"instagram", score:83, quality:"hot",  status:"demo_scheduled", intent:"demo_request",      team_size:18, pipeline:216000, created_at:"2026-05-04", city:"Pune" },
  { id:6,  name:"Deepa Nair",      company:"SecureLife IMF",        handle:"@securelife",      role:"Founder", lead_type:"IMF",   channel:"facebook",  score:71, quality:"hot",  status:"demo_done",      intent:"positive_signal",   team_size:6,  pipeline:72000,  created_at:"2026-05-07", city:"Kochi" },
  { id:7,  name:"Arun Gupta",      company:"SafeGuard Brokers",     handle:"@safeguard",       role:"CEO", lead_type:"broker",    channel:"facebook",  score:85, quality:"hot",  status:"converted",      intent:"demo_request",      team_size:30, pipeline:360000, created_at:"2026-05-05", city:"Mumbai" },
  { id:8,  name:"Kavitha Reddy",   company:"PrimeCover Agency",     handle:"@primecover",      role:"Owner", lead_type:"agent",   channel:"instagram", score:74, quality:"hot",  status:"demo_scheduled", intent:"feature_query",     team_size:3,  pipeline:36000,  created_at:"2026-05-08", city:"Hyderabad" },
  { id:9,  name:"Suresh Joshi",    company:"InsureLine Brokers",    handle:"@insureline",      role:"Partner", lead_type:"broker", channel:"facebook",  score:91, quality:"hot",  status:"demo_scheduled", intent:"demo_request",      team_size:25, pipeline:300000, created_at:"2026-05-09", city:"Chennai" },
  { id:10, name:"Meena Iyer",      company:"AssuredPath IMF",       handle:"@assuredpath",     role:"CEO", lead_type:"IMF",       channel:"instagram", score:76, quality:"hot",  status:"needs_human",    intent:"pricing_query",     team_size:10, pipeline:120000, created_at:"2026-05-10", city:"Bangalore" },
  // ── WARM (20) ─────────────────────────────────────────────────
  { id:11, name:"Rohit Kapoor",    company:"NextGen Insurance",     handle:"@nextgen",         role:"Director", lead_type:"broker",channel:"facebook", score:62, quality:"warm", status:"interested",     intent:"feature_query",     team_size:7,  pipeline:84000,  created_at:"2026-05-04", city:"Delhi" },
  { id:12, name:"Anita Desai",     company:"SafeNet IMF",           handle:"@safenet",         role:"Founder", lead_type:"IMF",   channel:"instagram", score:55, quality:"warm", status:"engaged",        intent:"pricing_query",     team_size:4,  pipeline:48000,  created_at:"2026-05-05", city:"Mumbai" },
  { id:13, name:"Manoj Tiwari",    company:"BharatCover Brokers",   handle:"@bharatcover",     role:"MD", lead_type:"broker",     channel:"facebook",  score:68, quality:"warm", status:"contacted",      intent:"onboarding_query",  team_size:12, pipeline:144000, created_at:"2026-05-06", city:"Lucknow" },
  { id:14, name:"Pooja Khanna",    company:"StarShield Agency",     handle:"@starshield",      role:"Owner", lead_type:"agent",   channel:"instagram", score:48, quality:"warm", status:"interested",     intent:"positive_signal",   team_size:2,  pipeline:24000,  created_at:"2026-05-07", city:"Jaipur" },
  { id:15, name:"Sanjay Verma",    company:"RiskGuard IMF",         handle:"@riskguard",       role:"CEO", lead_type:"IMF",       channel:"facebook",  score:65, quality:"warm", status:"contacted",      intent:"feature_query",     team_size:9,  pipeline:108000, created_at:"2026-05-08", city:"Kolkata" },
  { id:16, name:"Lata Mishra",     company:"SecurePlus Brokers",    handle:"@secureplus",      role:"Partner", lead_type:"broker",channel:"facebook", score:57, quality:"warm", status:"engaged",        intent:"pricing_query",     team_size:5,  pipeline:60000,  created_at:"2026-05-09", city:"Bhopal" },
  { id:17, name:"Ravi Pillai",     company:"CoverAll IMF",          handle:"@coverall",        role:"Founder", lead_type:"IMF",   channel:"instagram", score:60, quality:"warm", status:"interested",     intent:"onboarding_query",  team_size:6,  pipeline:72000,  created_at:"2026-05-10", city:"Trivandrum" },
  { id:18, name:"Geeta Choudhary", company:"PolicyMax Agency",      handle:"@policymax",       role:"Director", lead_type:"corporate",channel:"facebook",score:44,quality:"warm",status:"engaged",        intent:"feature_query",     team_size:8,  pipeline:96000,  created_at:"2026-05-11", city:"Chandigarh" },
  { id:19, name:"Nikhil Banerjee", company:"SafeHaven Brokers",     handle:"@safehaven",       role:"MD", lead_type:"broker",     channel:"instagram", score:67, quality:"warm", status:"contacted",      intent:"demo_request",      team_size:14, pipeline:168000, created_at:"2026-05-12", city:"Kolkata" },
  { id:20, name:"Rekha Agarwal",   company:"InsureTech IMF",        handle:"@insuretech",      role:"Founder", lead_type:"IMF",   channel:"facebook",  score:51, quality:"warm", status:"interested",     intent:"pricing_query",     team_size:3,  pipeline:36000,  created_at:"2026-05-12", city:"Agra" },
  { id:21, name:"Kiran Rao",       company:"ValueCover Brokers",    handle:"@valuecover",      role:"CEO", lead_type:"broker",    channel:"facebook",  score:63, quality:"warm", status:"engaged",        intent:"positive_signal",   team_size:11, pipeline:132000, created_at:"2026-05-13", city:"Hyderabad" },
  { id:22, name:"Smita Kulkarni",  company:"AnchorLife IMF",        handle:"@anchorlife",      role:"Owner", lead_type:"IMF",     channel:"instagram", score:47, quality:"warm", status:"interested",     intent:"onboarding_query",  team_size:5,  pipeline:60000,  created_at:"2026-05-14", city:"Pune" },
  { id:23, name:"Tarun Bhatia",    company:"SafeFirst Brokers",     handle:"@safefirst",       role:"Director", lead_type:"broker",channel:"facebook",score:58, quality:"warm", status:"contacted",      intent:"feature_query",     team_size:16, pipeline:192000, created_at:"2026-05-15", city:"Chandigarh" },
  { id:24, name:"Usha Krishnan",   company:"TrustLife IMF",         handle:"@trustlife",       role:"Founder", lead_type:"IMF",   channel:"instagram", score:66, quality:"warm", status:"engaged",        intent:"pricing_query",     team_size:7,  pipeline:84000,  created_at:"2026-05-15", city:"Chennai" },
  { id:25, name:"Vivek Sharma",    company:"PolicyPlus Agency",     handle:"@policyplus",      role:"Owner", lead_type:"agent",   channel:"facebook",  score:42, quality:"warm", status:"new",            intent:"greeting",          team_size:1,  pipeline:12000,  created_at:"2026-05-16", city:"Varanasi" },
  { id:26, name:"Nisha Dubey",     company:"GuardianCover Brokers", handle:"@guardiancover",   role:"MD", lead_type:"broker",     channel:"instagram", score:54, quality:"warm", status:"interested",     intent:"positive_signal",   team_size:9,  pipeline:108000, created_at:"2026-05-17", city:"Nagpur" },
  { id:27, name:"Prakash Nair",    company:"LifeShield IMF",        handle:"@lifeshield",      role:"CEO", lead_type:"IMF",       channel:"facebook",  score:61, quality:"warm", status:"engaged",        intent:"feature_query",     team_size:4,  pipeline:48000,  created_at:"2026-05-18", city:"Kochi" },
  { id:28, name:"Seema Bajaj",     company:"CoverMax Brokers",      handle:"@covermax",        role:"Partner", lead_type:"broker", channel:"instagram", score:69, quality:"warm", status:"contacted",      intent:"demo_request",      team_size:20, pipeline:240000, created_at:"2026-05-19", city:"Delhi" },
  { id:29, name:"Anil Saxena",     company:"ProShield Agency",      handle:"@proshield",       role:"Director", lead_type:"corporate",channel:"facebook",score:46,quality:"warm",status:"new",            intent:"greeting",          team_size:3,  pipeline:36000,  created_at:"2026-05-20", city:"Indore" },
  { id:30, name:"Bhavna Mehta",    company:"InsureRight IMF",       handle:"@insureright",     role:"Founder", lead_type:"IMF",   channel:"instagram", score:53, quality:"warm", status:"interested",     intent:"pricing_query",     team_size:6,  pipeline:72000,  created_at:"2026-05-20", city:"Surat" },
  // ── COLD (16) ─────────────────────────────────────────────────
  { id:31, name:"Chandan Singh",   company:"BasicCover Agency",     handle:"@basiccover",      role:"Owner", lead_type:"agent",   channel:"facebook",  score:32, quality:"cold", status:"engaged",        intent:"objection_cost",    team_size:1,  pipeline:12000,  created_at:"2026-05-06", city:"Patna" },
  { id:32, name:"Divya Joshi",     company:"SimplePlan IMF",        handle:"@simpleplan",      role:"Founder", lead_type:"IMF",   channel:"instagram", score:25, quality:"cold", status:"new",            intent:"greeting",          team_size:2,  pipeline:24000,  created_at:"2026-05-07", city:"Bhopal" },
  { id:33, name:"Eshwar Naidu",    company:"LowCost Brokers",       handle:"@lowcost",         role:"Director", lead_type:"broker",channel:"facebook", score:38, quality:"cold", status:"engaged",        intent:"objection_timing",  team_size:4,  pipeline:48000,  created_at:"2026-05-08", city:"Vijayawada" },
  { id:34, name:"Farida Malik",    company:"SmartCover POSP",       handle:"@smartcover",      role:"Agent", lead_type:"posp",    channel:"instagram", score:18, quality:"cold", status:"new",            intent:"greeting",          team_size:1,  pipeline:8000,   created_at:"2026-05-09", city:"Lucknow" },
  { id:35, name:"Gopal Yadav",     company:"BasicShield Agency",    handle:"@basicshield",     role:"Owner", lead_type:"agent",   channel:"facebook",  score:22, quality:"cold", status:"engaged",        intent:"objection_switching",team_size:1, pipeline:12000,  created_at:"2026-05-10", city:"Kanpur" },
  { id:36, name:"Hema Rajan",      company:"InsureBasic IMF",       handle:"@insurebasic",     role:"Founder", lead_type:"IMF",   channel:"instagram", score:34, quality:"cold", status:"new",            intent:"greeting",          team_size:3,  pipeline:36000,  created_at:"2026-05-11", city:"Mysore" },
  { id:37, name:"Iqbal Shaikh",    company:"LitePlan Brokers",      handle:"@liteplan",        role:"MD", lead_type:"broker",     channel:"facebook",  score:28, quality:"cold", status:"lost",           intent:"not_interested",    team_size:5,  pipeline:60000,  created_at:"2026-05-12", city:"Pune" },
  { id:38, name:"Jyoti Pandey",    company:"StarterIMF",            handle:"@starterimf",      role:"Founder", lead_type:"IMF",   channel:"instagram", score:15, quality:"cold", status:"lost",           intent:"not_interested",    team_size:2,  pipeline:24000,  created_at:"2026-05-13", city:"Allahabad" },
  { id:39, name:"Kishore Reddy",   company:"SimpleShield POSP",     handle:"@simpleshield",    role:"Agent", lead_type:"posp",    channel:"facebook",  score:36, quality:"cold", status:"engaged",        intent:"objection_cost",    team_size:1,  pipeline:8000,   created_at:"2026-05-14", city:"Hyderabad" },
  { id:40, name:"Lalitha Venkat",  company:"BasicGuard Agency",     handle:"@basicguard",      role:"Owner", lead_type:"agent",   channel:"instagram", score:20, quality:"cold", status:"new",            intent:"greeting",          team_size:1,  pipeline:12000,  created_at:"2026-05-16", city:"Coimbatore" },
  { id:41, name:"Mohan Das",       company:"SmallBiz Brokers",      handle:"@smallbiz",        role:"Director", lead_type:"broker",channel:"facebook", score:30, quality:"cold", status:"engaged",        intent:"objection_timing",  team_size:6,  pipeline:72000,  created_at:"2026-05-17", city:"Chennai" },
  { id:42, name:"Nalini Suresh",   company:"MicroCover IMF",        handle:"@microcover",      role:"Founder", lead_type:"IMF",   channel:"instagram", score:26, quality:"cold", status:"new",            intent:"greeting",          team_size:2,  pipeline:24000,  created_at:"2026-05-18", city:"Bangalore" },
  { id:43, name:"Om Prakash",      company:"EasyShield Agency",     handle:"@easyshield",      role:"Owner", lead_type:"agent",   channel:"facebook",  score:14, quality:"cold", status:"lost",           intent:"not_interested",    team_size:1,  pipeline:12000,  created_at:"2026-05-19", city:"Jaipur" },
  { id:44, name:"Parveen Akhtar",  company:"LiteCover POSP",        handle:"@litecover",       role:"Agent", lead_type:"posp",    channel:"instagram", score:33, quality:"cold", status:"engaged",        intent:"pricing_query",     team_size:1,  pipeline:8000,   created_at:"2026-05-20", city:"Amritsar" },
  { id:45, name:"Qamar Hussain",   company:"StartFresh IMF",        handle:"@startfresh",      role:"Founder", lead_type:"IMF",   channel:"facebook",  score:21, quality:"cold", status:"new",            intent:"greeting",          team_size:3,  pipeline:36000,  created_at:"2026-05-22", city:"Lucknow" },
  { id:46, name:"Rina Ghosh",      company:"SmallTeam Brokers",     handle:"@smallteam",       role:"MD", lead_type:"broker",     channel:"instagram", score:37, quality:"cold", status:"engaged",        intent:"objection_switching",team_size:8, pipeline:96000,  created_at:"2026-05-23", city:"Kolkata" },
  // ── NEW (10) ──────────────────────────────────────────────────
  { id:47, name:"Sameer Khanna",   company:"FreshStart Agency",     handle:"@freshstart",      role:"Owner", lead_type:"agent",   channel:"facebook",  score:5,  quality:"new",  status:"new",            intent:"greeting",          team_size:1,  pipeline:12000,  created_at:"2026-05-24", city:"Delhi" },
  { id:48, name:"Tanvi Patel",     company:"NewBroker Co",          handle:"@newbroker",       role:"Founder", lead_type:"broker",channel:"instagram", score:8,  quality:"new",  status:"new",            intent:"greeting",          team_size:2,  pipeline:24000,  created_at:"2026-05-24", city:"Ahmedabad" },
  { id:49, name:"Udit Sharma",     company:"FirstStep IMF",         handle:"@firststep",       role:"Founder", lead_type:"IMF",   channel:"facebook",  score:3,  quality:"new",  status:"new",            intent:"greeting",          team_size:1,  pipeline:12000,  created_at:"2026-05-25", city:"Bhopal" },
  { id:50, name:"Vanita Singh",    company:"NewAge POSP",           handle:"@newage",          role:"Agent", lead_type:"posp",    channel:"instagram", score:6,  quality:"new",  status:"new",            intent:"greeting",          team_size:1,  pipeline:8000,   created_at:"2026-05-25", city:"Pune" },
  { id:51, name:"Wasim Khan",      company:"FreshBrokers Ltd",      handle:"@freshbrokers",    role:"Director", lead_type:"broker",channel:"facebook", score:9,  quality:"new",  status:"new",            intent:"greeting",          team_size:3,  pipeline:36000,  created_at:"2026-05-26", city:"Mumbai" },
  { id:52, name:"Xenil Desai",     company:"StartIMF",              handle:"@startimf",        role:"Founder", lead_type:"IMF",   channel:"instagram", score:4,  quality:"new",  status:"new",            intent:"greeting",          team_size:2,  pipeline:24000,  created_at:"2026-05-26", city:"Vadodara" },
  { id:53, name:"Yamini Reddy",    company:"NewCover Agency",       handle:"@newcover",        role:"Owner", lead_type:"agent",   channel:"facebook",  score:7,  quality:"new",  status:"new",            intent:"greeting",          team_size:1,  pipeline:12000,  created_at:"2026-05-27", city:"Hyderabad" },
  { id:54, name:"Zara Sheikh",     company:"FreshShield POSP",      handle:"@freshshield",     role:"Agent", lead_type:"posp",    channel:"instagram", score:2,  quality:"new",  status:"new",            intent:"greeting",          team_size:1,  pipeline:8000,   created_at:"2026-05-27", city:"Pune" },
  { id:55, name:"Ajay Malhotra",   company:"StartBrokers",          handle:"@startbrokers",    role:"MD", lead_type:"broker",     channel:"facebook",  score:8,  quality:"new",  status:"new",            intent:"greeting",          team_size:4,  pipeline:48000,  created_at:"2026-05-28", city:"Delhi" },
  { id:56, name:"Bindu Nair",      company:"NewIMF Co",             handle:"@newimf",          role:"Founder", lead_type:"IMF",   channel:"instagram", score:5,  quality:"new",  status:"new",            intent:"greeting",          team_size:2,  pipeline:24000,  created_at:"2026-05-28", city:"Kochi" },
];

LEADS.forEach(l => l.avatar = avatar(l.name));

/* ── TEAM: humans who pick up handoffs from ARIA ───────────────── */
const TEAM = {
  aakash: { name:'Aakash', role:'Head of Sales',     avatar: avatar('Aakash Sales', 'avataaars') },
  priya:  { name:'Priya',  role:'Customer Success',  avatar: avatar('Priya CSM',    'avataaars') },
  riya:   { name:'Riya',   role:'Onboarding Lead',   avatar: avatar('Riya Onboard', 'avataaars') },
  kunal:  { name:'Arnav',  role:'Founder',          avatar: ME.avatar },
};

/* assign each lead to a team owner (CRM-style "deal owner") */
const OWNER_ROTATION = ['aakash','kunal','priya','riya'];
LEADS.forEach((l, i) => {
  if (l.quality === 'new') { l.owner = null; return; }
  l.owner = OWNER_ROTATION[i % OWNER_ROTATION.length];
});

/* "minutes ago" since last activity — feels live, CRM-style */
const ACTIVITY_OFFSETS = [4, 12, 22, 37, 58, 90, 142, 220, 360, 540, 720, 1200];
LEADS.forEach((l, i) => l.last_activity_min = ACTIVITY_OFFSETS[i % ACTIVITY_OFFSETS.length]);

/* Priority actions on the overview right rail */
const PRIORITY_ITEMS = [
  { icon:'flame',   tone:'warm',   title:'Hot lead just qualified', meta:'May 28', progress:'3/3 actions', desc:'Rajesh @ AssuredMax (88 score) booked a demo for Monday. Confirm slot.' },
  { icon:'check',   tone:'mint',   title:'Demo confirmed',          meta:'May 27', progress:'1/2 follow-ups', desc:'Priya @ ShieldFirst attended demo. Send pricing deck before EOD.' },
  { icon:'call',    tone:'rose',   title:'Pricing objection',       meta:'May 26', progress:'1/3 actions',   desc:'Sunita @ ProtectPlus asked about Plan A vs B. ARIA queued a response.' },
  { icon:'sparkle', tone:'violet', title:'Re-engagement window',    meta:'May 25', progress:'0/2 nudges',    desc:'4 warm leads silent for 72h. ARIA will resend approved drafts at 9am.' },
];

const CHART_START = '2026-05-01';
const CHART_END   = '2026-05-28';
const FOCUS_DAY   = '2026-05-14';

/* ── INBOX: conversations (12 sample threads) ───────────────────────
   Some threads include a handoff_at marker — when a lead escalated to
   the team, the conversation continues with `human` messages so the
   teammate picks up exactly where ARIA left off. */
const CONVERSATIONS = [
  {
    lead_id: 1, unread: 0, last_at: '14:30',
    handoff_at: '14:00', handed_to: 'aakash',
    messages: [
      { from:'lead', text:"Hi! Saw your ad. We're a 15-broker outfit in Mumbai, looking for software to manage policies + commissions.", t:'10:42' },
      { from:'aria', text:"Hi Rajesh, glad you reached out! BeyondSure is built exactly for that — broker portal, policy CRM, IRDAI-compliant commissions. Quick q: do you currently use anything?", t:'10:43' },
      { from:'lead', text:"We use Excel sheets and email chains. It's chaos honestly.", t:'10:48' },
      { from:'aria', text:"Most brokers we onboard say the same thing. Would Friday 11am work for a 20-min walkthrough?", t:'10:49' },
      { from:'lead', text:"Actually, can I speak to someone on your team? Need to discuss multi-branch licensing.", t:'13:55' },
      { from:'aria', text:"Of course — Aakash from our team will jump in here in a moment. He'll have full context on what we've discussed.", t:'13:56' },
      // ── ARIA hands off to Aakash ──
      { from:'human', who:'aakash', text:"Hi Rajesh, Aakash here. Saw your note on multi-branch — we support unlimited branches under one Plan B license. How many branches are we talking?", t:'14:00' },
      { from:'lead', text:"Three. Mumbai, Pune, Ahmedabad.", t:'14:24' },
      { from:'human', who:'aakash', text:"Perfect. Plan B covers all three. Want to lock in Monday 11am for the team walkthrough?", t:'14:26' },
      { from:'lead', text:"Yes, Monday works.", t:'14:28' },
      { from:'human', who:'aakash', text:"Confirmation just went to your email. See you Monday!", t:'14:30' },
    ],
  },
  {
    lead_id: 2, unread: 2, last_at: '1d',
    messages: [
      { from:'lead', text:"Just finished the demo. Loved the dashboard. Pricing?", t:'Yesterday' },
      { from:'aria', text:"Glad you liked it! Plan B at ₹48,380/yr fits an IMF your size — covers up to 25 sub-agents.", t:'Yesterday' },
      { from:'lead', text:"Can we get a custom plan? We're at 8 but growing fast.", t:'Yesterday' },
    ],
  },
  {
    lead_id: 4, unread: 1, last_at: '2d',
    handoff_at: 'Yesterday', handed_to: 'priya',
    messages: [
      { from:'lead', text:"What's the difference between Plan A and Plan B?", t:'2 days ago' },
      { from:'aria', text:"Plan A is ₹24,780/yr for up to 5 users — great for solo agencies. Plan B at ₹48,380/yr unlocks team workflows + custom branding.", t:'2 days ago' },
      { from:'lead', text:"Can someone call me to walk through it?", t:'2 days ago' },
      { from:'aria', text:"Absolutely — I'm pulling in Priya from our CSM team. She'll have the full thread.", t:'Yesterday' },
      // ── ARIA hands off to Priya ──
      { from:'human', who:'priya', text:"Hi Sunita! Priya here. Best slots this week: Tue 4pm or Thu 11am. Which works?", t:'Yesterday' },
    ],
  },
  {
    lead_id: 11, unread: 0, last_at: '3d',
    messages: [
      { from:'lead', text:"Does it integrate with policy bazaar?", t:'3 days ago' },
      { from:'aria', text:"Yes — via our API or CSV import. Most brokers sync nightly. Want a demo?", t:'3 days ago' },
    ],
  },
  {
    lead_id: 13, unread: 0, last_at: '4d',
    messages: [
      { from:'lead', text:"Looking for software, found you on FB. Send pricing.", t:'4 days ago' },
      { from:'aria', text:"Hey Manoj! Quick q first — broker, IMF, or agent? That changes the recommendation.", t:'4 days ago' },
      { from:'lead', text:"Broker. 12 in the team.", t:'4 days ago' },
    ],
  },
  {
    lead_id: 6, unread: 0, last_at: '5d',
    messages: [
      { from:'lead', text:"Hi, demo went well. Discussing internally.", t:'5 days ago' },
      { from:'aria', text:"Thanks Deepa! I'll check back in a week. Anything I can clarify in the meantime?", t:'5 days ago' },
    ],
  },
  {
    lead_id: 19, unread: 0, last_at: '6d',
    handoff_at: '6 days ago', handed_to: 'kunal',
    messages: [
      { from:'lead', text:"Can I get a demo this week? Also have questions about white-label billing.", t:'6 days ago' },
      { from:'aria', text:"Yes! White-label billing is custom — I'll loop in Kunal who handles partnership pricing.", t:'6 days ago' },
      // ── ARIA hands off to Kunal ──
      { from:'human', who:'kunal', text:"Hi Nikhil — Kunal here. For white-label, we have a partner tier. Let's hop on a call. Thursday 3pm or Friday 11am?", t:'6 days ago' },
      { from:'lead', text:"Friday works.", t:'6 days ago' },
    ],
  },
  {
    lead_id: 21, unread: 0, last_at: '1w',
    messages: [
      { from:'lead', text:"Looks promising. What's your onboarding like?", t:'1 week ago' },
      { from:'aria', text:"7-day white-glove setup — dedicated CSM, data import, branded portal. We handle ~90% of it.", t:'1 week ago' },
    ],
  },
  {
    lead_id: 28, unread: 0, last_at: '9d',
    messages: [
      { from:'lead', text:"Interested. Send a demo invite.", t:'9 days ago' },
      { from:'aria', text:"On it. Sharing a chat link — pick a slot that works.", t:'9 days ago' },
    ],
  },
  {
    lead_id: 31, unread: 0, last_at: '12d',
    messages: [
      { from:'lead', text:"Too expensive for a single agency like mine.", t:'12 days ago' },
      { from:'aria', text:"Totally hear you Chandan — Plan A is built for solo agencies at ₹24,780/yr. Effectively ₹2k/mo. Worth a look?", t:'12 days ago' },
    ],
  },
  {
    lead_id: 33, unread: 0, last_at: '14d',
    messages: [
      { from:'lead', text:"Maybe next quarter. Year-end is busy.", t:'2 weeks ago' },
      { from:'aria', text:"Fair. I'll set a reminder for August 1st and check in. No pressure!", t:'2 weeks ago' },
    ],
  },
  {
    lead_id: 37, unread: 0, last_at: '16d',
    messages: [
      { from:'lead', text:"Already using something. Not switching.", t:'16 days ago' },
      { from:'aria', text:"Understood Iqbal. If anything changes, I'm here. Best of luck!", t:'16 days ago' },
    ],
  },
];

/* attach lead info into each conversation for quick rendering */
CONVERSATIONS.forEach(c => {
  c.lead = LEADS.find(l => l.id === c.lead_id);
  c.preview = c.messages[c.messages.length - 1].text;
  c.escalated = !!c.handoff_at;
});

/* ── OPERATING STATUS: what's the team's co-pilot doing right now ── */
const OPERATING_STATUS = {
  monitoring: 24,    // active conversations ARIA is watching
  drafting: 3,       // replies in progress
  decisions: [
    {
      icon: 'inbox',    tone: 'mint',
      title: '7 drafts pending review',
      meta: '3 are for hot leads (score ≥ 80)',
      cta: 'Review now',  goto: 'approvals',
    },
    {
      icon: 'handoff',  tone: 'rose',
      title: '3 leads asked for a human',
      meta: 'Rajesh K. · Sunita P. · Nikhil B. waiting',
      cta: 'Open inbox',  goto: 'inbox',
    },
    {
      icon: 'clock',    tone: 'violet',
      title: '5 follow-ups queued for 9 am IST',
      meta: 'Re-engagement window opens in 14 hrs',
      cta: 'View queue',  goto: 'analytics',
    },
  ],
  today: [
    { val: 23, lbl: 'drafts written' },
    { val: 14, lbl: 'sent (after approval)' },
    { val: 89, lbl: 'leads scored' },
    { val:  6, lbl: 'hot alerts fired' },
  ],
};

/* ── APPROVALS: pending drafts ──────────────────────────────────── */
const PENDING_DRAFTS = [
  {
    id: 'd1', lead_id: 11, intent: 'pricing_query', created_at: '2026-05-28T11:42',
    subject: 'Re: BeyondSure — Rohit',
    body: "Hi Rohit, thanks for checking in! BeyondSure's Plan B (₹48,380/yr) is the sweet spot for a 7-broker team — unlimited policy management, custom-branded portal, and commission auto-reconciliation. I can have our team walk you through it on a 20-min call. Wednesday 3pm or Friday 11am?",
  },
  {
    id: 'd2', lead_id: 17, intent: 'onboarding_query', created_at: '2026-05-28T10:18',
    subject: 'Re: BeyondSure — Ravi',
    body: "Hey Ravi! Onboarding takes about a week. Our team handles the data migration, sets up your branded portal, and trains your team. You'd be live by next Friday. Want to lock in a kickoff?",
  },
  {
    id: 'd3', lead_id: 4, intent: 'pricing_query', created_at: '2026-05-27T16:30',
    subject: 'Re: BeyondSure — Sunita',
    body: "Hi Sunita, Plan A is ₹24,780/yr (5 users) and Plan B is ₹48,380/yr (25 users + team workflows). For ProtectPlus at 5 people, Plan A covers you for now and you can upgrade anytime. Free 14-day trial?",
  },
  {
    id: 'd4', lead_id: 22, intent: 'feature_query', created_at: '2026-05-27T14:15',
    subject: 'Re: BeyondSure — Smita',
    body: "Hi Smita! Yes — we support both motor and health policies natively, plus commercial lines via our IRDAI module. Renewals are automated 30 days out. Want a quick demo to see it in action?",
  },
  {
    id: 'd5', lead_id: 26, intent: 'positive_signal', created_at: '2026-05-27T09:00',
    subject: 'Follow-up — Nisha',
    body: "Hey Nisha, just checking in! You mentioned interest in BeyondSure last week. Anything I can clarify, or should we set up a call with the team?",
  },
  {
    id: 'd6', lead_id: 12, intent: 'pricing_query', created_at: '2026-05-26T17:22',
    subject: 'Re: BeyondSure — Anita',
    body: "Hi Anita! For a 4-person IMF, Plan A at ₹24,780/yr fits perfectly. Comes with policy CRM, commission tracking, and our broker portal. Free trial available — 14 days, no card needed.",
  },
  {
    id: 'd7', lead_id: 15, intent: 'feature_query', created_at: '2026-05-26T13:45',
    subject: 'Re: BeyondSure — Sanjay',
    body: "Hey Sanjay, RiskGuard handles 9 brokers — Plan B's team workflow features will save your team ~4 hours/week on commission reconciliation alone. Quick walkthrough on Tuesday?",
  },
];

/* ── ANALYTICS: precomputed snapshots ─────────────────────────── */
const ANALYTICS = {
  totalPipelineValue: 2480000,
  mom: { leads: +12, demos: +6, conversion: +2.4, pipeline: -8 },
  funnel: [
    { stage: 'Form submitted', count: 168, pct: 100 },
    { stage: 'First-touch sent', count: 156, pct: 93 },
    { stage: 'Replied', count: 89,  pct: 53 },
    { stage: 'Qualified',     count: 56,  pct: 33 },
    { stage: 'Demo booked',   count: 18,  pct: 11 },
    { stage: 'Won',           count: 6,   pct: 4  },
  ],
  sources: [
    { name: 'Facebook',   count: 31, color: '#1877f2' },
    { name: 'Instagram',  count: 25, color: '#e6683c' },
  ],
  scoreBuckets: [
    {b:'0–20', n:14}, {b:'20–40',n:12}, {b:'40–60',n:11}, {b:'60–80',n:10}, {b:'80–100',n:9},
  ],
  weeklyTrend: [
    { w:'W1', leads:11, demos:4 },
    { w:'W2', leads:13, demos:5 },
    { w:'W3', leads:14, demos:5 },
    { w:'W4', leads:18, demos:4 },
  ],
  cohorts: [
    { week:'May 1–7',  leads:11, contacted:10, replied:7, demos:3, won:1 },
    { week:'May 8–14', leads:13, contacted:13, replied:8, demos:5, won:2 },
    { week:'May 15–21',leads:14, contacted:13, replied:6, demos:5, won:2 },
    { week:'May 22–28',leads:18, contacted:14, replied:5, demos:4, won:1 },
  ],
};
