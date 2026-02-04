# Certification Management & SHA-256 Verification

This document explains how to manage certifications using the admin panel and how the SHA-256 hash verification system works.

---

## Table of Contents

1. [Admin Panel Access](#admin-panel-access)
2. [Adding a New Certification](#adding-a-new-certification)
3. [Managing Certifications](#managing-certifications)
   - [Status Control](#status-control)
   - [Visibility Control](#visibility-control)
   - [Deleting Certifications](#deleting-certifications)
4. [SHA-256 Hash Verification](#sha-256-hash-verification)
5. [Viewing and Managing Certifications](#viewing-and-managing-certifications)
6. [Verification Page](#verification-page)
7. [Security Considerations](#security-considerations)

---

## Admin Panel Access

### Prerequisites

- Admin account credentials (see `docs/admin-setup.md`)
- Valid email and password configured in `.env`

### Logging In

1. Navigate to **http://localhost:8000/admin/login**
2. Enter your admin email and password
3. Click **"Sign in"**
4. You'll be redirected to the certifications management page

### Protected Routes

All admin routes require authentication:

| Route | Description |
|-------|-------------|
| `/admin/login` | Login page (public) |
| `/admin/certs` | Certification management |
| `/admin/status` | System status dashboard |

---

## Adding a New Certification

### Step-by-Step Guide

#### 1. Access the Admin Panel

Visit **http://localhost:8000/admin/certs** (you'll be redirected to login if not authenticated)

#### 2. Fill Out the Form

The certification upload form requires:

| Field | Description | Required | Example |
|-------|-------------|----------|---------|
| **Slug** | URL-friendly identifier | Yes | `ckad` |
| **Title** | Human-readable certification name | Yes | `Certified Kubernetes Application Developer` |
| **Issuer** | Organization that issued the cert | Yes | `The Linux Foundation` |
| **PDF File** | The certification PDF document | Yes | `ckad.pdf` |
| **Verification URL** | External verification link | No | `https://ti-user-certificates.s3.amazonaws.com/...` |
| **Assertion URL** | Open Badges assertion URL | No | `https://api.badgr.io/public/assertions/...` |

#### 3. Upload the PDF

1. Click **"Choose File"** and select your certification PDF
2. Ensure the PDF is:
   - Legitimate and authentic
   - Under 10MB (recommended)
   - In PDF format (`.pdf` extension)

#### 4. Submit the Form

1. Review all fields for accuracy
2. Click **"Add Certification"**
3. The system will:
   - Save the PDF to `fitness/static/certs/{slug}.pdf`
   - Calculate the SHA-256 hash
   - Create a database entry
   - Return you to the certifications list

#### 5. Verify the Upload

The certification will appear in the admin table with:
- Title and issuer badge
- Slug identifier
- Links to view PDF, verification page, and Open Badges (if applicable)

---

## Managing Certifications

Once certifications are added, the admin panel provides comprehensive management tools to control their status, visibility, and lifecycle.

### Status Control

Each certification can have one of three statuses:

| Status | Icon | Meaning | Use Case |
|--------|------|---------|----------|
| **Active** | ✓ | Current, valid certification | Certifications you currently hold and want to display |
| **Deprecated** | ⚠ | No longer maintained but kept for historical records | Certifications you've renewed or are no longer pursuing |
| **Expired** | ✗ | Certification has expired and is no longer valid | Time-limited certs that have expired |

#### Changing Status

1. In the admin certifications table, locate the **Status** column
2. Click the dropdown for the certification you want to update
3. Select the new status: **Active**, **Deprecated**, or **Expired**
4. The page will refresh automatically with the updated status

**Visual Indicators:**
- **Active certifications** have a green left border and green-tinted dropdown
- **Deprecated certifications** have a yellow left border and yellow-tinted dropdown
- **Expired certifications** have a red left border and red-tinted dropdown

### Visibility Control

Visibility determines whether a certification appears in public listings. This is independent of status, allowing flexible control.

| Visibility | Icon | Meaning |
|------------|------|---------|
| **Public** | 👁️ | Visible in public certifications page |
| **Hidden** | 🔒 | Only visible in admin panel |

#### Common Combinations

- **Active + Public** → Normal public certification display
- **Active + Hidden** → Preparing to publish (uploaded but not yet shown)
- **Deprecated + Public** → Publicly show it's deprecated (transparency)
- **Deprecated + Hidden** → Historical record only
- **Expired + Public** → Show expired status to visitors
- **Expired + Hidden** → Archive expired cert without public display

#### Toggling Visibility

1. In the admin certifications table, locate the **Visibility** column
2. Click the visibility button (shows current state: "👁️ Public" or "🔒 Hidden")
3. The page will refresh automatically with the toggled visibility

**Visual Indicators:**
- Hidden certifications appear faded/grayed out in the admin table
- Only **public** certifications appear on `/certs` page
- Hidden certifications are completely excluded from public view

### Deleting Certifications

Permanent deletion removes the certification from the database and deletes the PDF file.

⚠️ **WARNING:** Deletion cannot be undone. Consider using **Status: Deprecated** or **Visibility: Hidden** instead to preserve historical records.

#### How to Delete

1. In the admin certifications table, locate the **Actions** column
2. Click the **🗑️ Delete** button for the certification
3. Confirm the deletion in the popup dialog
4. The certification will be removed from the database
5. The PDF file will be deleted from `fitness/static/certs/`

#### What Gets Deleted

- ✗ Database entry (all metadata)
- ✗ PDF file (`fitness/static/certs/{slug}.pdf`)
- ✗ All verification links become invalid

#### Alternatives to Deletion

Instead of permanently deleting, consider:
- **Set Status to Deprecated** - Keep historical record
- **Set Visibility to Hidden** - Remove from public view
- **Both** - Hide and mark as deprecated for complete archival

---

## SHA-256 Hash Verification

### What is SHA-256?

**SHA-256** (Secure Hash Algorithm 256-bit) is a cryptographic hash function that creates a unique "fingerprint" for a file.

**Key Properties:**
- **Deterministic**: Same file always produces the same hash
- **Unique**: Different files produce different hashes (collision-resistant)
- **One-way**: Cannot reverse-engineer the file from the hash
- **Sensitive**: Even a single byte change produces a completely different hash

### How the Hash is Generated

#### Code Location: `fitness/routers/admin.py:23-28`

```python
def hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
```

**Process:**
1. Opens the PDF in **binary read mode**
2. Reads in **8KB chunks** (efficient for large files)
3. Feeds each chunk to SHA-256 hasher
4. Returns **64-character hexadecimal digest**

**Example Output:**
```text
a3f5c9b2e1d4f8a7c6b3e9d2f1a8c5b4d7e3f9a2b8c1d6e4f2a9b7c3d5e8f1a6
```

### When is the Hash Calculated?

#### On Upload (Admin Panel): `fitness/routers/admin.py:98`

```python
storage = LocalStorage(Path("fitness/static/certs"), settings.base_url)
filename = f"{slug}.pdf"
url = await storage.save(file.file, filename)
sha = hash_file(Path("fitness/static/certs") / filename)  # ← Hash generated here
cert = Certification(
    slug=slug,
    title=title,
    issuer=issuer,
    pdf_url=url,
    sha256=sha,  # ← Stored in database
    ...
)
```

#### On Startup (Existing PDFs): `fitness/main.py:75-87`

```python
for pdf_path in cert_dir.glob("*.pdf"):
    ...
    sha256_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    certification = Certification(
        slug=slug,
        ...
        sha256=sha256_hash,
        ...
    )
```

---

## Verification Page

### Accessing Verification Pages

Each certification has a dedicated verification page at:

```text
https://yourdomain.com/v/{slug}
```

**Examples:**
- `/v/ckad` - CKAD certification
- `/v/pmp` - PMP certification
- `/v/aws-saa` - AWS Solutions Architect

### What's Displayed

The verification page (`fitness/templates/verification.html`) shows:

1. **Certification Details**
   - Title
   - Issuer
   - Creation date

2. **SHA-256 Hash**
   ```html
   <span class="label">SHA-256:</span>
   <code class="hash">a3f5c9b2e1d4f8a7...</code>
   ```

3. **Action Buttons**
   - Download PDF
   - External Verification Link (if provided)
   - Open Badges Assertion (if provided)

### Independent Verification

Anyone can verify the PDF's authenticity:

#### Step 1: Visit Verification Page

```text
https://engage.princetonstrong.online/v/ckad
```

#### Step 2: Copy the SHA-256 Hash

```text
a3f5c9b2e1d4f8a7c6b3e9d2f1a8c5b4d7e3f9a2b8c1d6e4f2a9b7c3d5e8f1a6
```

#### Step 3: Download the PDF

Click **"Download PDF"** or visit:
```text
https://engage.princetonstrong.online/static/certs/ckad.pdf
```

#### Step 4: Calculate the Hash

**On Linux/macOS:**
```bash
sha256sum ckad.pdf
```

**On Windows (PowerShell):**
```powershell
Get-FileHash ckad.pdf -Algorithm SHA256
```

**Expected Output:**
```text
a3f5c9b2e1d4f8a7c6b3e9d2f1a8c5b4d7e3f9a2b8c1d6e4f2a9b7c3d5e8f1a6  ckad.pdf
```

#### Step 5: Compare

- **Match** → PDF is authentic and unmodified
- **No match** → PDF has been tampered with or corrupted

---

## Viewing and Managing Certifications

### Admin Dashboard

Visit **http://localhost:8000/admin/certs** to see all certifications in a table:

| Issuer | Title | Slug | Actions |
|--------|-------|------|---------|
| The Linux Foundation | Certified Kubernetes... | ckad | PDF \| Verify \| Badges |

### Public Certifications Page

Visit **http://localhost:8000/certs** to see the public-facing certifications gallery:

- Cards with issuer badges
- Clickable PDFs
- Verification links
- QR codes for mobile scanning

### Deduplication

The system automatically prevents duplicate certifications:

**Code:** `fitness/routers/ui.py:98-100`
```python
seen_hashes = set()
for cert in all_certs:
    if cert.sha256 in seen_hashes:
        continue  # Skip duplicate
    seen_hashes.add(cert.sha256)
```

**Result:** Same PDF uploaded multiple times only appears once.

---

## Security Considerations

### Why SHA-256 is Secure

1. **Collision Resistance**
   - Probability of two different PDFs having the same hash: ~1 in 2^256
   - Computationally infeasible to find collisions

2. **Pre-image Resistance**
   - Cannot create a PDF that matches a given hash
   - Protects against forgery

3. **Avalanche Effect**
   - Single bit change → completely different hash
   - Detects even tiny modifications

### Limitations

1. **Not a Signature**
   - SHA-256 proves integrity, not authenticity
   - Doesn't prove *who* created the PDF
   - Complement with external verification URLs

2. **Requires Trusted Source**
   - Hash must be published on a trusted platform
   - If attacker controls both PDF and hash, verification fails
   - Use HTTPS and secure admin access

3. **No Timestamp Proof**
   - Hash doesn't prove *when* PDF was created
   - Consider adding creation timestamps to verification page

### Best Practices

1. **Always use HTTPS** in production (`ENVIRONMENT=production`)
2. **Protect admin credentials** (strong passwords, 2FA if available)
3. **Provide external verification links** when available
4. **Regularly audit certifications** for legitimacy
5. **Use Open Badges** for standards-compliant verification
6. **Publish hashes publicly** on your verification pages
7. **Encourage third-party verification** (link to this doc!)

---

## Troubleshooting

### "Duplicate certification detected"

**Cause:** A PDF with the same SHA-256 hash already exists

**Solution:** This is working as intended. If you need to update metadata, delete the existing entry first (not currently supported in UI - use database directly or add delete feature)

### "File upload failed"

**Cause:** File size too large or wrong format

**Solution:**
- Ensure file is a PDF
- Compress PDF if over 10MB
- Check disk space on server

### "Hash mismatch when verifying"

**Cause:** PDF was modified after upload or download was corrupted

**Solution:**
- Re-download the PDF
- Clear browser cache
- Verify you're comparing the correct file

---

## API Endpoints

### Upload Certification

```http
POST /admin/certs
Content-Type: multipart/form-data
Authorization: Cookie (session)

slug=ckad
title=Certified Kubernetes Application Developer
issuer=The Linux Foundation
file=@ckad.pdf
verification_url=https://...
assertion_url=https://...
csrf_token=...
```

### View Verification Page

```http
GET /v/{slug}
```

**Response:** HTML page with SHA-256 hash and download links

---

## Database Schema

Certifications are stored in the `certifications` table:

```sql
CREATE TABLE certifications (
    id INTEGER PRIMARY KEY,
    slug VARCHAR(255) UNIQUE,
    title VARCHAR(255),
    issuer VARCHAR(255),
    pdf_url VARCHAR(1024),
    sha256 VARCHAR(128),        -- 64-char hex hash
    dns_name VARCHAR(255),      -- Optional DNS TXT record
    verification_url VARCHAR(1024),
    assertion_url VARCHAR(1024),
    created_at TIMESTAMP
);
```

---

## Related Documentation

- [Admin Setup Guide](admin-setup.md) - How to configure admin authentication
- [Open Badges Integration](https://www.imsglobal.org/sites/default/files/Badges/OBv2p0Final/index.html) - Open Badges 2.0 specification

---

## Example Workflow

### Complete Certification Upload Process

```bash
# 1. Log in to admin panel
open http://localhost:8000/admin/login

# 2. Fill out form
Slug: ckad
Title: Certified Kubernetes Application Developer
Issuer: The Linux Foundation
File: ckad.pdf
Verification URL: https://ti-user-certificates.s3.amazonaws.com/...
Assertion URL: (leave blank)

# 3. Submit form
# System generates SHA-256: a3f5c9b2e1d4f8a7c6b3e9d2f1a8c5b4...

# 4. Verify the upload
open http://localhost:8000/v/ckad

# 5. Third-party verification
curl -O http://localhost:8000/static/certs/ckad.pdf
sha256sum ckad.pdf
# Output: a3f5c9b2e1d4f8a7c6b3e9d2f1a8c5b4... ckad.pdf ✓ MATCH!
```

---

**Last Updated:** 2025-11-15
**Author:** Princeton A. Strong
**License:** MIT
