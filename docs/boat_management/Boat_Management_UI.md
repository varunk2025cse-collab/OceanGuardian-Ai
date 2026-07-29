# Boat Management UI Design
**OceanGuardian AI — Flutter & Dashboard UX Specification**
**Version:** 1.0

---

## 1. Design Principles

- **Tamil-first:** All labels, buttons, and status messages in Tamil with English fallback
- **Sunlight readable:** High contrast, minimum 4.5:1 ratio, tested at 1000 lux
- **Large touch targets:** Minimum 48×48dp for all interactive elements
- **Offline-first:** Every screen shows data from local cache when offline, with a clear OFFLINE banner
- **Low literacy:** Icons + short labels, never text-only status
- **Elderly fishermen:** Font size minimum 16sp body, 20sp headings, no small print
- **WCAG 2.1 AA:** Screen reader support, no color-only indicators, keyboard navigable

---

## 2. Screen Inventory

| Screen | Route | Role |
|---|---|---|
| Boat List | `/boats` | fisherman, operator |
| Boat Detail | `/boats/:id` | all |
| Register Boat | `/boats/register` | fisherman |
| Edit Boat | `/boats/:id/edit` | fisherman, admin |
| Boat Documents | `/boats/:id/documents` | fisherman, operator |
| Upload Document | `/boats/:id/documents/upload` | fisherman |
| Crew Management | `/boats/:id/crew` | fisherman, operator |
| Equipment Checklist | `/boats/:id/equipment` | fisherman, operator |
| Maintenance Records | `/boats/:id/maintenance` | fisherman, operator |
| Boat History | `/boats/:id/history` | fisherman, operator, admin |
| QR Code | `/boats/:id/qr` | fisherman, operator |
| Inspection Status | `/boats/:id/inspections` | fisherman, operator |
| Trip Readiness | `/boats/:id/readiness` | fisherman |
| Fleet View (Dashboard) | `/fleet` | operator, admin |

---

## 3. Screen Specifications

### 3.1 Boat List Screen

**Purpose:** Primary entry point for boat management.

**Layout:**
```
┌─────────────────────────────────────────┐
│ [←]  என் படகுகள் / My Boats    [+ பதிவு]│
│─────────────────────────────────────────│
│ [OFFLINE BANNER — shown when offline]   │
│─────────────────────────────────────────│
│ ┌─────────────────────────────────────┐ │
│ │ 🚢 முருகன் கடல்                     │ │
│ │ TN-MFB-2024-001                     │ │
│ │ ● ACTIVE  ✓ VERIFIED  🏥 82/100     │ │
│ │ நாகப்பட்டினம் துறைமுகம்             │ │
│ │ [Trip Readiness: READY ✓]           │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ┌─────────────────────────────────────┐ │
│ │ 🚢 ராஜன் வலை                        │ │
│ │ TN-MFB-2023-088                     │ │
│ │ ⚠ MAINTENANCE  ✓ VERIFIED  🏥 45/100│ │
│ │ [Trip Readiness: NOT READY ✗]       │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Status badge colors + icons (never color alone):**
- ACTIVE: green + ● icon
- MAINTENANCE: amber + 🔧 icon
- EMERGENCY: red + 🚨 icon (pulsing)
- INACTIVE: grey + ○ icon
- LOST: red + ? icon
- DAMAGED: orange + ⚠ icon
- DECOMMISSIONED: grey + ✕ icon

**Accessibility:**
- Each card has a semantic label: "Boat Murugan Kadal, status Active, health score 82 out of 100, tap to view details"
- Status badge has `Semantics(label: 'Status: Active')` wrapper

---

### 3.2 Boat Detail Screen

**Purpose:** Full boat information hub with quick actions.

**Layout (scrollable):**
```
┌─────────────────────────────────────────┐
│ [←]  முருகன் கடல்              [✏ திருத்து]│
│─────────────────────────────────────────│
│ [Boat photo or placeholder image]       │
│ ● ACTIVE  ✓ VERIFIED                   │
│─────────────────────────────────────────│
│ QUICK ACTIONS (large buttons, 2×2 grid) │
│ ┌──────────────┐ ┌──────────────────┐   │
│ │ 🗺 பயண தயார்  │ │ 📄 ஆவணங்கள்      │   │
│ │ Trip Ready   │ │ Documents        │   │
│ └──────────────┘ └──────────────────┘   │
│ ┌──────────────┐ ┌──────────────────┐   │
│ │ 👥 குழுவினர்  │ │ 🔧 பராமரிப்பு    │   │
│ │ Crew         │ │ Maintenance      │   │
│ └──────────────┘ └──────────────────┘   │
│─────────────────────────────────────────│
│ VESSEL DETAILS                          │
│ பதிவு எண்: TN-MFB-2024-001             │
│ வகை: Mechanized                         │
│ நீளம்: 8.5m  அகலம்: 2.1m               │
│ இயந்திரம்: Kirloskar KD-10 (40 HP)     │
│ எரிபொருள்: 120L capacity               │
│─────────────────────────────────────────│
│ HEALTH SCORE                            │
│ [████████░░] 82/100 — Good              │
│ ⚠ Oil change due in 15 days            │
│─────────────────────────────────────────│
│ DOCUMENTS STATUS                        │
│ ✓ Fishing License — expires 2025-12-31 │
│ ✓ Insurance — expires 2025-06-30       │
│ ⚠ Inspection — due 2025-03-01         │
│─────────────────────────────────────────│
│ [QR குறியீடு காட்டு / Show QR Code]    │
└─────────────────────────────────────────┘
```

---

### 3.3 Register Boat Screen

**Purpose:** Step-by-step boat registration. Designed for low-literacy users.

**Flow:** 4 steps with progress indicator

```
Step 1: Basic Info
  - Boat name (required) — large text field
  - Registration number (optional) — with format hint "TN-MFB-YYYY-NNN"
  - Vessel class (dropdown with icons)
  - Color (color picker + text)

Step 2: Engine & Dimensions
  - Engine type (diesel/petrol/electric/sail — icon buttons)
  - Engine horsepower (number)
  - Fuel capacity (number + "liters" label)
  - Length, beam (optional)
  - Year built (year picker)

Step 3: Home Harbor
  - Harbor selector (searchable list with map preview)
  - "Use my current location to find nearest harbor" button

Step 4: Review & Submit
  - Summary of all entered data
  - "Submit for Verification" button
  - Offline note: "Will be submitted when you are online"
```

**Offline behavior:** Form data saved to local SQLite outbox. User sees "Saved — will register when online" confirmation.

---

### 3.4 Boat Documents Screen

**Purpose:** Manage compliance documents with expiry tracking.

**Layout:**
```
┌─────────────────────────────────────────┐
│ [←]  ஆவணங்கள் / Documents    [+ சேர்]  │
│─────────────────────────────────────────│
│ EXPIRY ALERTS                           │
│ ⚠ Insurance expires in 45 days         │
│─────────────────────────────────────────│
│ ✓ மீன்பிடி உரிமம் / Fishing License    │
│   No: TN-FL-2024-001234                 │
│   Expires: 2025-12-31  ✓ Verified      │
│   [View] [Download]                     │
│─────────────────────────────────────────│
│ ⚠ காப்பீடு / Insurance                 │
│   No: NIAC-2024-88821                   │
│   Expires: 2025-06-30  ✓ Verified      │
│   [View] [Download]                     │
│─────────────────────────────────────────│
│ ✗ ஆய்வு சான்றிதழ் / Inspection Cert.  │
│   Not uploaded                          │
│   [Upload Now]                          │
└─────────────────────────────────────────┘
```

**Document status icons:**
- ✓ green: valid and verified
- ⚠ amber: expiring within 60 days
- ✗ red: expired or missing

---

### 3.5 Crew Management Screen

**Purpose:** Assign and manage crew members.

**Layout:**
```
┌─────────────────────────────────────────┐
│ [←]  குழுவினர் / Crew          [+ சேர்] │
│─────────────────────────────────────────│
│ 👤 முருகன் K                            │
│    கேப்டன் / Captain  ★ Primary Contact │
│    📞 +91-9876543210                    │
│    [Remove]                             │
│─────────────────────────────────────────│
│ 👤 ராஜன் S                              │
│    Deckhand                             │
│    📞 +91-9876543211                    │
│    [Remove]                             │
│─────────────────────────────────────────│
│ ℹ Minimum 1 crew member required       │
│   for trip start                        │
└─────────────────────────────────────────┘
```

**Add Crew Dialog:**
- Search by phone number (finds registered users)
- Or enter name + phone manually (for non-registered crew)
- Role selector (icon + label)
- Primary contact toggle

---

### 3.6 Equipment Checklist Screen

**Purpose:** Safety equipment inventory with condition tracking.

**Layout:**
```
┌─────────────────────────────────────────┐
│ [←]  உபகரணங்கள் / Equipment   [+ சேர்] │
│─────────────────────────────────────────│
│ LIFE SAVING (உயிர் காக்கும்)            │
│ ✓ Life Jackets × 6    [Good ●]         │
│ ✓ Life Ring × 2       [Good ●]         │
│ ⚠ EPIRB × 1          [Fair ●]         │
│─────────────────────────────────────────│
│ FIRE SAFETY (தீ பாதுகாப்பு)            │
│ ✓ Fire Extinguisher × 2  [Good ●]     │
│─────────────────────────────────────────│
│ COMMUNICATION (தொடர்பு)                │
│ ✗ VHF Radio           [Missing ●]     │
│─────────────────────────────────────────│
│ CHECKLIST SCORE: 7/9 items OK          │
│ [Mark All Checked Today]               │
└─────────────────────────────────────────┘
```

**Condition colors + icons:**
- Good: green ●
- Fair: amber ●
- Poor: orange ●
- Missing: red ●

---

### 3.7 Trip Readiness Screen

**Purpose:** Pre-trip safety gate. Clear pass/fail with actionable items.

**Layout:**
```
┌─────────────────────────────────────────┐
│ [←]  பயண தயார்நிலை / Trip Readiness    │
│─────────────────────────────────────────│
│                                         │
│         ⚠ NOT READY                    │
│    பயணம் தொடங்க முடியாது               │
│                                         │
│─────────────────────────────────────────│
│ BLOCKING ISSUES (fix before trip)       │
│                                         │
│ ✗ மீன்பிடி உரிமம் காலாவதியானது        │
│   Fishing license expired Dec 31        │
│   [Renew Now →]                         │
│─────────────────────────────────────────│
│ WARNINGS (can proceed with caution)     │
│                                         │
│ ⚠ எரிபொருள் குறைவாக உள்ளது (18%)      │
│   Fuel below 20% — refuel recommended  │
│                                         │
│ ⚠ ஆய்வு 45 நாட்களில் தேவை            │
│   Inspection due in 45 days            │
│─────────────────────────────────────────│
│ PASSED CHECKS                           │
│ ✓ Boat status: Active                  │
│ ✓ Insurance: Valid                     │
│ ✓ Crew: 2 members assigned             │
│─────────────────────────────────────────│
│ AI Recommendation (confidence: 94%)     │
│ "Renew license at Nagapattinam Fisheries│
│  office before next trip."              │
│─────────────────────────────────────────│
│ [Refresh Check]                         │
└─────────────────────────────────────────┘
```

---

### 3.8 QR Code Screen

**Purpose:** Display and share boat QR code for field identification.

**Layout:**
```
┌─────────────────────────────────────────┐
│ [←]  QR குறியீடு / QR Code             │
│─────────────────────────────────────────│
│                                         │
│         [Large QR Code Image]           │
│                                         │
│    முருகன் கடல்                         │
│    TN-MFB-2024-001                      │
│    Owner: Murugan K                     │
│    Emergency: +91-9876543210            │
│                                         │
│─────────────────────────────────────────│
│ [📤 Share]  [🖨 Print]  [💾 Save]       │
│─────────────────────────────────────────│
│ ℹ This QR code can be scanned by       │
│   Coast Guard and rescue teams          │
└─────────────────────────────────────────┘
```

**Offline:** QR code is generated from local data — works fully offline.

---

### 3.9 Fleet View (Rescue Dashboard — React)

**Purpose:** Operator view of all boats with status and readiness.

**Layout:**
```
Fleet Overview
─────────────────────────────────────────────────────────
[Search boats...]  [Filter: Status ▼]  [Filter: Harbor ▼]

Summary Cards:
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ 98 ACTIVE│ │12 MAINT. │ │ 2 EMERG. │ │ 8 DOCS   │
│          │ │          │ │ ⚠ ALERT  │ │ EXPIRING │
└──────────┘ └──────────┘ └──────────┘ └──────────┘

Boat Cards Grid:
┌─────────────────────────────────────┐
│ 🚢 Murugan Kadal                    │
│ TN-MFB-2024-001  ● ACTIVE          │
│ Owner: Murugan K  Harbor: Nagapat. │
│ Health: ████████░░ 82/100           │
│ Trip: Active since 06:30            │
│ Docs: ✓ License ✓ Insurance        │
│ [View Details]                      │
└─────────────────────────────────────┘
```

---

## 4. Localization Strings (Tamil)

```
boat_list_title = "என் படகுகள்"
boat_register_cta = "படகு பதிவு செய்"
boat_status_active = "செயலில்"
boat_status_maintenance = "பராமரிப்பு"
boat_status_emergency = "அவசரநிலை"
boat_status_inactive = "செயலற்றது"
boat_status_lost = "காணவில்லை"
boat_status_damaged = "சேதமடைந்தது"
boat_status_decommissioned = "ஓய்வுபெற்றது"
trip_ready = "பயணம் தயார்"
trip_not_ready = "பயணம் தயாரில்லை"
documents_title = "ஆவணங்கள்"
crew_title = "குழுவினர்"
equipment_title = "உபகரணங்கள்"
maintenance_title = "பராமரிப்பு"
health_score_label = "படகு ஆரோக்கியம்"
qr_code_title = "QR குறியீடு"
offline_banner = "இணைப்பு இல்லை — சேமிக்கப்பட்ட தரவு காட்டப்படுகிறது"
license_expired = "மீன்பிடி உரிமம் காலாவதியானது"
insurance_expired = "காப்பீடு காலாவதியானது"
fuel_low = "எரிபொருள் குறைவாக உள்ளது"
```

---

## 5. Accessibility Checklist

- [ ] All interactive elements ≥ 48×48dp
- [ ] All text ≥ 16sp body, ≥ 20sp headings
- [ ] Color contrast ≥ 4.5:1 for normal text, ≥ 3:1 for large text
- [ ] No color-only status indicators (always icon + color + text)
- [ ] Screen reader labels on all icons and status badges
- [ ] Form fields have visible labels (not placeholder-only)
- [ ] Error messages are announced by screen reader
- [ ] Loading states announced: "Loading boat details"
- [ ] Offline state announced: "Showing saved data — no internet connection"
- [ ] Tamil strings tested with native speakers
- [ ] Tested with TalkBack (Android) and VoiceOver (iOS)
