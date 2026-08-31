"""Detailed farmer-facing disease guides (English).

Merged into advice_for() via knowledge.py. Each entry adds:
  description, next_steps[{title,detail}], when_to_call_helpline, expected_outcome
"""
from __future__ import annotations

from typing import Dict, List

DiseaseGuide = Dict[str, object]

DISEASE_GUIDES: Dict[str, DiseaseGuide] = {
    "healthy": {
        "description": (
            "The leaf shows no clear disease symptoms. Keep monitoring the field — "
            "early detection of spots, yellowing or mold prevents big losses."
        ),
        "next_steps": [
            {
                "title": "Confirm across plants",
                "detail": "Check 10–20 plants in different parts of the field, not only one leaf. Look under leaves and near the soil line.",
            },
            {
                "title": "Keep a simple field diary",
                "detail": "Note date, weather (rain/fog), and any insect activity. This helps if symptoms appear later.",
            },
            {
                "title": "Maintain balanced care",
                "detail": "Continue regular irrigation and fertiliser as recommended for your crop. Avoid excess nitrogen which can invite soft growth and disease.",
            },
            {
                "title": "Scout weekly",
                "detail": "Walk the field once a week. Photograph any new spots and scan again with AgroScan.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if neighbouring fields show sudden wilt, blight, or unusual insect outbreaks.",
        "expected_outcome": "Healthy growth if you keep scouting and avoid water stress or overcrowding.",
    },
    "apple_scab": {
        "description": (
            "Apple scab is a fungal disease. Spots start olive-green and become dark and velvety. "
            "It spreads fast in cool, wet weather and can ruin fruit quality."
        ),
        "next_steps": [
            {
                "title": "Remove and destroy infected leaves/fruit",
                "detail": "Pick up fallen leaves and scabby fruit. Do not leave them under the tree — burn or bury away from the orchard.",
            },
            {
                "title": "Improve air flow",
                "detail": "Prune crowded branches so leaves dry faster after rain or dew. Wet leaves for many hours favour the fungus.",
            },
            {
                "title": "Protect with fungicide (label dose)",
                "detail": "Use a protectant fungicide such as mancozeb or captan as allowed locally. Spray thoroughly on both leaf sides. Repeat as per label, especially after rain.",
            },
            {
                "title": "Plan resistant varieties next season",
                "detail": "Ask your local nursery/DAE for scab-resistant apple cultivars if you replant.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if more than ~30% leaves are spotted or fruit cracking is widespread.",
        "expected_outcome": "New spots slow within 1–2 weeks if sprays + sanitation are done; damaged fruit may not recover.",
    },
    "black_rot": {
        "description": (
            "Black rot fungi cause ‘frog-eye’ leaf spots and can rot fruit. Dead twigs and mummified fruit "
            "carry the fungus into the next season."
        ),
        "next_steps": [
            {
                "title": "Cut out cankers and mummies",
                "detail": "Remove dried fruit still hanging and prune dead/cankered wood. Disinfect pruning tools between cuts (alcohol or bleach solution).",
            },
            {
                "title": "Clean the ground",
                "detail": "Rake infected debris. Compost only if your pile gets hot; otherwise bury or burn away from the orchard.",
            },
            {
                "title": "Protective spray schedule",
                "detail": "From bloom onward, apply captan/mancozeb-type fungicides following the product label. Cover fruit clusters well.",
            },
            {
                "title": "Watch fruit closely",
                "detail": "Remove any fruit that starts to rot so spores do not splash onto healthy fruit.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if cankers keep returning on main trunks or young trees die back.",
        "expected_outcome": "Leaf spots stop spreading with sanitation + sprays; keep removing mummies every season.",
    },
    "rust": {
        "description": (
            "Rust diseases make orange or rusty pustules on leaves. Many types need moisture and sometimes "
            "an alternate host plant nearby."
        ),
        "next_steps": [
            {
                "title": "Confirm underside pustules",
                "detail": "Gently flip leaves — rusty powder underneath is typical. Avoid brushing it onto healthy plants.",
            },
            {
                "title": "Reduce leaf wetness",
                "detail": "Irrigate at the soil, not over the leaves. Water early morning so foliage dries the same day.",
            },
            {
                "title": "Fungicide at first signs",
                "detail": "Apply a recommended fungicide (e.g. myclobutanil-type products where registered for your crop). Follow the label interval.",
            },
            {
                "title": "Remove alternate hosts if relevant",
                "detail": "For cedar-apple type rusts, junipers near the orchard can keep the cycle going — ask an extension officer before removing trees.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if rust covers most of the canopy or yield drop is severe.",
        "expected_outcome": "New pustules decline after dry conditions + correct spray; heavily damaged leaves may drop.",
    },
    "powdery_mildew": {
        "description": (
            "Powdery mildew looks like white flour on leaves and shoots. Unlike many fungi it can grow "
            "in drier air, but dense shade and soft lush growth make it worse."
        ),
        "next_steps": [
            {
                "title": "Open the canopy",
                "detail": "Prune or space plants so sunlight and wind reach the leaves. Remove the worst-affected shoots.",
            },
            {
                "title": "Spray sulfur or bicarbonate (mild cases)",
                "detail": "Use agricultural sulfur or potassium bicarbonate sprays as labeled. Do not spray sulfur in very hot midday sun (leaf burn risk).",
            },
            {
                "title": "Escalate if needed",
                "detail": "For heavy infection, use a systemic fungicide approved for your crop. Rotate chemical groups if spraying repeatedly.",
            },
            {
                "title": "Ease off excess nitrogen",
                "detail": "Too much urea/N creates soft tissue that mildew loves. Balance with recommended fertiliser rates.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if mildew returns every week despite sprays, or fruit/flowers are badly damaged.",
        "expected_outcome": "White coating stops expanding in several days; severely coated leaves may not turn fully green again.",
    },
    "gray_leaf_spot": {
        "description": (
            "Gray leaf spot (Cercospora) on maize makes long rectangular lesions. In humid weather it can "
            "blight large parts of the leaf and cut grain fill."
        ),
        "next_steps": [
            {
                "title": "Decide if a spray is worth it",
                "detail": "If disease starts before or around tasseling and is moving up the plant, a foliar fungicide (strobilurin/triazole type) can protect yield. After dent stage, sprays rarely pay.",
            },
            {
                "title": "Spray correctly",
                "detail": "Use clean water, correct dose, and good coverage on mid/upper leaves. Follow pre-harvest interval on the label.",
            },
            {
                "title": "Plan rotation and hybrids",
                "detail": "Next season: rotate away from maize if possible and choose hybrids with gray leaf spot resistance.",
            },
            {
                "title": "Manage residue",
                "detail": "After harvest, plough or bury infected stalks so spores do not survive easily on the surface.",
            },
        ],
        "when_to_call_helpline": "Call 16123 for spray product choice if lesions are racing up to the ear leaf.",
        "expected_outcome": "Sprays protect remaining green leaf; already dead tissue will not recover.",
    },
    "northern_leaf_blight": {
        "description": (
            "Northern leaf blight makes long cigar-shaped tan lesions on maize. Cool, wet weather helps it spread "
            "and can reduce yield if the ear leaf is damaged early."
        ),
        "next_steps": [
            {
                "title": "Scout the ear leaf zone",
                "detail": "If lesions are below the ear and moving slowly, monitor every 3–4 days. If they reach the ear leaf before tasseling/silking, consider fungicide.",
            },
            {
                "title": "Apply fungicide when justified",
                "detail": "Use a maize-labelled fungicide at early disease onset. One well-timed spray often beats late repeated sprays.",
            },
            {
                "title": "Choose resistant hybrids next year",
                "detail": "Ask dealers/DAE for NLB-resistant hybrids suited to your district.",
            },
            {
                "title": "Rotate and bury residue",
                "detail": "Avoid maize-after-maize when possible. Incorporate stalk residue after harvest.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if more than half the plants show lesions on or above the ear leaf.",
        "expected_outcome": "Progress slows after spray + drier weather; expect better grain fill if the ear leaf stays green.",
    },
    "esca": {
        "description": (
            "Esca (black measles) is a grape trunk disease complex. Leaves may show tiger-stripe patterns; "
            "vines can collapse suddenly. There is no reliable chemical cure."
        ),
        "next_steps": [
            {
                "title": "Mark affected vines",
                "detail": "Paint or tag vines with tiger-stripe leaves or sudden wilt so you can track them each season.",
            },
            {
                "title": "Remove dead arms carefully",
                "detail": "Cut back to healthy wood in dry weather. Protect large pruning wounds with a wound sealant recommended for grape.",
            },
            {
                "title": "Do not stress the vineyard",
                "detail": "Avoid waterlogging, severe drought, and oversized crops on weak vines.",
            },
            {
                "title": "Replant strategy",
                "detail": "Severely declining vines may need replacement with clean planting material. Ask a grape specialist via 16123/DAE.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if many vines collapse in one season or you need pruning/wound-protect guidance.",
        "expected_outcome": "Disease is chronic; good pruning hygiene slows spread but infected trunks may keep declining.",
    },
    "leaf_blight": {
        "description": (
            "Grape leaf blight (Isariopsis-type) causes dark irregular leaf spots and early leaf drop, "
            "which weakens vines and exposes fruit to sunburn."
        ),
        "next_steps": [
            {
                "title": "Remove fallen infected leaves",
                "detail": "Clear leaves under the trellis so spores do not splash up in rain.",
            },
            {
                "title": "Protective fungicide",
                "detail": "Apply mancozeb or copper fungicides on a protectant schedule in wet periods. Cover both leaf surfaces.",
            },
            {
                "title": "Canopy management",
                "detail": "Shoot thinning and leaf pulling (as appropriate for your trellis) improve drying and spray coverage.",
            },
            {
                "title": "Reassess after rain",
                "detail": "Heavy rain washes protectants — reapply according to the label if the wet spell continues.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if defoliation is severe before harvest.",
        "expected_outcome": "New spotting slows with dry weather + sprays; lost leaves will not regrow the same season.",
    },
    "citrus_greening": {
        "description": (
            "Citrus greening (HLB) is a serious bacterial disease spread by the Asian citrus psyllid. "
            "There is no cure. Infected trees decline and produce bitter, lopsided fruit."
        ),
        "next_steps": [
            {
                "title": "Get a second confirmation",
                "detail": "Compare blotchy yellow patterns (asymmetric) with nutrient yellowing (often more even). If unsure, contact DAE/16123 before removing trees.",
            },
            {
                "title": "Remove confirmed infected trees",
                "detail": "Uproot and destroy infected trees to protect the rest of the orchard. Do not leave stumps that resprout.",
            },
            {
                "title": "Control psyllids",
                "detail": "Use recommended insecticides and monitor flush growth where psyllids feed. Yellow sticky traps help monitoring.",
            },
            {
                "title": "Plant only certified clean saplings",
                "detail": "Never buy unmarked roadside plants. Ask for disease-free certified citrus planting material.",
            },
        ],
        "when_to_call_helpline": "Call 16123 immediately if you suspect greening in a productive orchard — early removal protects neighbours too.",
        "expected_outcome": "Infected trees will not recover; healthy trees stay productive only if vectors and inoculum are controlled.",
    },
    "bacterial_spot": {
        "description": (
            "Bacterial spot makes small water-soaked spots that turn brown/black, often with yellow halos. "
            "It spreads in rain splash and when you work plants while wet. Chemicals only slow it."
        ),
        "next_steps": [
            {
                "title": "Stop working wet plants",
                "detail": "Do not prune, harvest, or walk rows when leaves are wet — you can spread bacteria on tools and clothes.",
            },
            {
                "title": "Remove worst plants/leaves",
                "detail": "Pull severely infected plants. For light cases, remove the worst leaves and destroy them away from the plot.",
            },
            {
                "title": "Copper sprays (limited help)",
                "detail": "Copper bactericides can slow new infection. Follow label rates; overuse can injure leaves. They will not erase existing spots.",
            },
            {
                "title": "Change seed and rotation",
                "detail": "Next season use certified clean seed/seedlings and rotate away from tomato/pepper for 2+ years if possible.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if seedlings in a nursery tray are collapsing or fruit lesions make the crop unsaleable.",
        "expected_outcome": "Spread slows in dry weather; spotted leaves stay marked but new growth can be cleaner.",
    },
    "early_blight": {
        "description": (
            "Early blight (Alternaria) starts on older leaves with target-like brown rings. It is common in "
            "warm weather and after heavy leaf wetting. Fruit can also be scarred near the stem."
        ),
        "next_steps": [
            {
                "title": "Strip lower infected leaves",
                "detail": "Remove the worst lower leaves and destroy them. Wash hands/tools after. Improve airflow at the base.",
            },
            {
                "title": "Mulch the soil",
                "detail": "Straw or plastic mulch reduces soil splash that carries spores onto leaves.",
            },
            {
                "title": "Fungicide cover",
                "detail": "Apply chlorothalonil or mancozeb-type fungicides as labeled. Spray undersides of leaves. Repeat after rain as directed.",
            },
            {
                "title": "Support and spacing",
                "detail": "Stake/trellis tomatoes, avoid overhead irrigation, and do not crowd plants.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if lesions jump to green fruit or plants defoliate before harvest.",
        "expected_outcome": "Lower-leaf epidemic usually slows in 7–10 days with sanitation + sprays; keep protecting new growth.",
    },
    "late_blight": {
        "description": (
            "Late blight (Phytophthora) is an emergency disease of tomato and potato. Grey-green water-soaked "
            "patches can destroy a field in days during cool, humid, foggy weather."
        ),
        "next_steps": [
            {
                "title": "Act the same day",
                "detail": "Do not wait. If late blight is confirmed or strongly suspected, prepare a fungicide spray immediately and isolate the worst plants.",
            },
            {
                "title": "Spray a suitable fungicide",
                "detail": "Use products labelled for late blight (e.g. protectants like chlorothalonil/mancozeb; follow local guidance for systemic mixes). Cover all foliage. Respect harvest waiting periods.",
            },
            {
                "title": "Destroy hotspots",
                "detail": "Pull and bag badly infected plants. Do not compost. Keep cull piles far from potato/tomato fields.",
            },
            {
                "title": "Warn neighbours and avoid wet work",
                "detail": "Spores travel on wind. Tell nearby growers. Avoid walking fields when plants are wet.",
            },
            {
                "title": "Next planting",
                "detail": "Use certified seed tubers/seedlings and resistant varieties. Never save seed from a blighted crop.",
            },
        ],
        "when_to_call_helpline": "Call 16123 today if lesions are spreading across multiple plants — this disease needs urgent advice.",
        "expected_outcome": "Fast action can save remaining green tissue; delayed action often means total crop loss.",
    },
    "leaf_mold": {
        "description": (
            "Tomato leaf mold thrives in high humidity (poly-tunnels, dense plantings). Pale spots appear on "
            "the upper leaf with olive velvety mold underneath."
        ),
        "next_steps": [
            {
                "title": "Ventilate and lower humidity",
                "detail": "Open greenhouse sides/vents. Reduce overnight humidity. Space plants and prune suckers for airflow.",
            },
            {
                "title": "Stop wetting the foliage",
                "detail": "Switch to drip or base watering. Water in the morning.",
            },
            {
                "title": "Remove infected leaves",
                "detail": "Pick moldy leaves, bag them, and take them out of the house/tunnel.",
            },
            {
                "title": "Fungicide if still spreading",
                "detail": "Apply a labelled fungicide for leaf mold. Combine with humidity control or sprays will disappoint.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if a whole poly-tunnel is yellowing despite ventilation.",
        "expected_outcome": "Mold stops producing new spots when humidity drops; damaged leaves remain scarred.",
    },
    "septoria_leaf_spot": {
        "description": (
            "Septoria causes many small round spots with dark borders and tiny black dots in the centre. "
            "It usually climbs from the bottom of the tomato plant upward."
        ),
        "next_steps": [
            {
                "title": "Remove lower infected leaves",
                "detail": "Strip leaves with many spots up to the first fruit cluster if needed. Destroy debris.",
            },
            {
                "title": "Mulch and stake",
                "detail": "Keep fruit and foliage off bare soil. Stake plants and prune for air movement.",
            },
            {
                "title": "Protectant fungicides",
                "detail": "Chlorothalonil/mancozeb programmes work if started early and repeated per label after rain.",
            },
            {
                "title": "Irrigation change",
                "detail": "Avoid overhead sprinklers. Keep night leaf wetness as short as possible.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if spots reach the upper canopy before fruits mature.",
        "expected_outcome": "Progression up the plant slows; expect cleaner new leaves above the cleaned zone.",
    },
    "spider_mites": {
        "description": (
            "Two-spotted spider mites are tiny pests, not a fungus. They suck leaf sap, leaving fine yellow "
            "stippling and sometimes silk webbing. Hot, dry, dusty conditions favour outbreaks."
        ),
        "next_steps": [
            {
                "title": "Confirm with a white paper test",
                "detail": "Tap a leaf over white paper — moving pepper-like dots suggest mites. Check undersides with a phone magnifier if you have one.",
            },
            {
                "title": "Hose the undersides",
                "detail": "A strong water spray under leaves knocks mites down. Repeat every 2–3 days for a week for light infestations.",
            },
            {
                "title": "Use soap, neem, or a miticide",
                "detail": "Insecticidal soap or neem oil on undersides helps. For heavy outbreaks use a labelled miticide — regular insecticides often fail and kill mite predators.",
            },
            {
                "title": "Reduce plant stress",
                "detail": "Keep soil moisture steady and reduce dust along field edges. Avoid unnecessary broad-spectrum sprays.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if webbing covers many plants or leaves bronze and drop quickly.",
        "expected_outcome": "Populations fall within a week of repeated undersurface treatments; stippled leaves may stay scarred.",
    },
    "target_spot": {
        "description": (
            "Target spot (Corynespora) makes brown lesions with concentric rings on tomato leaves and can "
            "scar fruit. Warm humid weather favours it."
        ),
        "next_steps": [
            {
                "title": "Sanitation first",
                "detail": "Remove heavily spotted leaves and any infected fruit. Clear old crop debris from the bed.",
            },
            {
                "title": "Fungicide programme",
                "detail": "Apply chlorothalonil or mancozeb-type products with good coverage. Rotate modes of action if spraying often.",
            },
            {
                "title": "Airflow and watering",
                "detail": "Stake plants, avoid leaf wetness, and water at the base early in the day.",
            },
            {
                "title": "Rotate next season",
                "detail": "Do not follow tomato with tomato/potato in the same bed if disease was heavy.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if fruit lesions make marketing impossible or seedlings are dying.",
        "expected_outcome": "New lesions slow after 1–2 spray cycles plus drier foliage.",
    },
    "mosaic_virus": {
        "description": (
            "Tomato mosaic and related viruses cause mottled leaves and distorted growth. Viruses are not "
            "killed by fungicides. They spread on hands, tools, and sometimes seed or insects."
        ),
        "next_steps": [
            {
                "title": "Remove infected plants",
                "detail": "Pull plants with clear mosaic/distortion and destroy them. Do not compost.",
            },
            {
                "title": "Disinfect tools and hands",
                "detail": "Wash with soap. Tools can be dipped in a mild bleach solution or milk solution used by growers for TMV hygiene — rinse after.",
            },
            {
                "title": "Avoid tobacco near the crop",
                "detail": "Tobacco users should wash hands before touching tomatoes; TMV-related viruses can transfer.",
            },
            {
                "title": "Replant with resistant varieties",
                "detail": "Choose resistant cultivars and clean seed. Control weeds that host viruses.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if a whole nursery bed shows mosaic — you may need to discard the lot.",
        "expected_outcome": "Infected plants will not heal; protecting healthy plants prevents further spread.",
    },
    "yellow_leaf_curl_virus": {
        "description": (
            "TYLCV causes upward leaf curl, yellow margins, stunting and flower drop. Whiteflies spread it. "
            "There is no spray that cures an infected plant."
        ),
        "next_steps": [
            {
                "title": "Rogue infected plants early",
                "detail": "Remove curled/stunted plants as soon as you see them so whiteflies do less virus spread.",
            },
            {
                "title": "Control whiteflies",
                "detail": "Use yellow sticky traps, reflective mulch if available, and labelled insecticides carefully. Focus on the underside of leaves.",
            },
            {
                "title": "Protect seedlings",
                "detail": "Raise seedlings under fine insect netting. Do not transplant from an infested nursery.",
            },
            {
                "title": "Use resistant varieties next time",
                "detail": "Ask for TYLCV-resistant tomato hybrids suited to Bangladesh conditions.",
            },
        ],
        "when_to_call_helpline": "Call 16123 if whitefly clouds and curl symptoms appear together across the field.",
        "expected_outcome": "Infected plants stay unproductive; early rogueing + whitefly control protects later plantings.",
    },
}


def guide_for(kb_key: str) -> Dict[str, object] | None:
    return DISEASE_GUIDES.get(kb_key)
