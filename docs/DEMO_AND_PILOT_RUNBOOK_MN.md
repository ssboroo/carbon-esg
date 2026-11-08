# CARBON ESG — Demo ба pilot runbook

**Шалгасан огноо:** 2026-11-08  
**Төлөв:** main салбарт интеграцлагдсан MVP; production approval биш.

## 1. Одоогийн бодит боломж

Одоогоор үндсэн `main` салбарт дараах функцууд нэгтгэгдсэн:

- Neon Managed Auth-д зориулсан бүртгүүлэх/нэвтрэх урсгал, API дээр EdDSA JWT шалгалт.
- Баталгаажсан хэрэглэгчийн байгууллага үүсгэх, өөрийн байгууллагуудын жагсаалтыг харах.
- PostgreSQL tenant schema, transaction-local RLS context, tenant тусгаарлах composite foreign key.
- Тайлант inventory үүсгэх, жагсаах.
- Баталгаажсан emission factor сонгох, activity record үүсгэх, Decimal тооцоолол.
- Үр дүнгийн immutable calculation snapshot болон audit event.
- Emission factor бүртгэх, хараат бус owner/admin review хийх, approve/reject.
- Монгол хэлний workspace, factor registry болон review UI.

**Гэхдээ** код нэгтгэгдсэн нь үйлчилгээ бодит орчинд ажиллаж байна гэсэн үг биш. Neon production/dev DB migration, Render deployment, Neon Auth trusted origin, нэвтрэлт ба бүх урсгалын end-to-end туршилт хараахан баталгаажаагүй. Иймд одоогоор хэрэглэгчийн бодит мэдээлэл оруулахгүй.

## 2. Архитектур ба үйлчилгээний тохиргоо

- Web: Next.js Node runtime (auth cookie болон dynamic workspace шаардлагатай).
- API: FastAPI.
- Database: PostgreSQL/Neon; migration-д тусдаа credential, runtime-д RLS bypass эрхгүй role.
- Auth: Neon Managed Auth JWT; private cookie secret нь зөвхөн server-side environment variable.
- Hosting: Render Blueprint preview боломжтой боловч deployment болон үнэгүй tier-ийн өнөөгийн нөхцөлийг тусад нь баталгаажуулна.

Шаардлагатай environment variables-ийг `apps/api/.env.example`, `apps/web/.env.example`, `render.yaml`-аас шалга. Бодит утгыг GitHub-д хэзээ ч commit хийхгүй.

## 3. Local development

### API

```bash
cd apps/api
python -m venv .venv
# Өөрийн OS-д тохируулан virtual environment идэвхжүүл
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### Web

```bash
cd apps/web
cp .env.example .env.local
# Neon Auth болон NEXT_PUBLIC_API_URL-ийг зөвхөн local/dev утгаар тохируул
npm install
npm run dev
```

Web: `http://localhost:3000`; API: `http://localhost:8000`.

### CI шалгалт

GitHub Actions дээр API tests, Alembic offline SQL validation, TypeScript check, Next.js production build ажиллана. CI амжилттай болсон нь бодит Neon/Render environment, auth provider эсвэл tenant isolation staging дээр баталгаажсан гэсэн үг биш.

## 4. Demo урсгал

1. Монгол хэлний sign-up хуудсаар туршилтын хэрэглэгч үүсгэнэ.
2. Нэвтэрч байгууллага үүсгэнэ.
3. Тайлант хугацаа сонгож inventory үүсгэнэ.
4. Emission factor-ийн эх сурвалж, HTTPS URL, газарзүйн хамрах хүрээ, он, нэгж, хувилбар болон утгыг эх сурвалжаас шалган бүртгэнэ.
5. Өөр owner/admin хэрэглэгч factor-ийг review note-тойгоор approve/reject хийнэ. Бүртгэгч өөрийн factor-ийг өөрөө батлах ёсгүй.
6. Зөвхөн approved/verified factor сонгон activity record оруулна.
7. API-аас буцсан Scope 1/2 тооцоолол, factor provenance, calculation history-г үзүүлнэ.

Хэрэв баталгаажсан factor байхгүй бол тоон үр дүн зохиож үзүүлэхгүй. Системийн empty state-ийг харуулна. AI-аар гаргасан factor value-г тооцооллын оролт болгохгүй.

## 5. Demo үед заавал хэлэх хязгаарлалт

- Энэ хувилбар Scope 1/2 суурь урсгалтай; Scope 3 бүрэн бүртгэл, үнэлгээний систем биш.
- Scope 2 location-based болон market-based аргыг тус тусад нь хадгалж тайлагнах бүрэн model хараахан хэрэгжээгүй. Хоёр хувилбарыг нэг нийлбэр болгохгүй.
- GRI 102: Climate Change 2025-ийн бүх шаардлага (gas-level breakdown, biogenic emissions, base-year/recalculation, comparative periods гэх мэт) одоогоор хангагдаагүй.
- Evidence Vault, malware scan, private object storage, retention болон backup/restore баталгаажаагүй.
- Хараат бус assurance, legal opinion, GRI/IFRS/GHG Protocol conformity эсвэл Монголын зохицуулалтын бүрэн нийцэл гэж сурталчлахгүй.

## 6. Go-live gate — бодит байгууллага оруулахаас өмнө

- Тусгаарласан Neon development branch үүсгэж migration-ийг тэнд турших.
- Runtime DB role нь `NOSUPERUSER`, `NOBYPASSRLS`, table owner биш гэдгийг SQL-аар батлах.
- Migration role ба runtime role-ийн эрхийг тусгаарлах.
- Хоёр өөр хэрэглэгч/байгууллагаар cross-tenant read/write тест хийх.
- Signup → organization → inventory → factor submit → independent review → activity → calculation → audit урсгалыг staging дээр бүрэн ажиллуулах.
- Auth trusted origin, cookie/session expiry, sign-out болон iOS Safari behavior-ийг шалгах.
- Scope 2 method model, GRI 102:2025 disclosure, factor provenance, gas/GWP model болон report/export-г хэрэгжүүлж тестлэх.
- Evidence storage, malware scanning, backup/restore, monitoring, rate limiting, incident response, data retention-ийг шийдэх.
- Монголын хууль, стандартын хүчин төгөлдөр байдал болон тайлангийн аргачлалыг мэргэжлийн хүнээр хянуулах.

## 7. Аюулгүй demo data

- Зөвхөн synthetic байгууллага, хэрэглэгч, activity data ашигла.
- Бодит хэрэглэгчийн мэдээлэл, банк/гэрээний баримт, нууц үг, token, database URL оруулахгүй.
- Албан ёсны эх сурвалжгүй emission factor зохиож seed хийхгүй.
- Demo тооцооллыг баталгаажсан тайлан эсвэл assurance statement гэж нэрлэхгүй.

## 8. Үнэгүй орчны нөхцөл

Render/Neon free tier нь sleep, compute, storage, connection болон usage хязгаартай байж болно. Deploy хийх өдөр provider-ийн албан ёсны pricing/limits-ийг шалга. Free tier-ийн нөхцөл баталгаажаагүй бол paid resource автоматаар үүсгэхгүй. Custom domain худалдан авах шаардлагагүй.

## 9. Албан ёсны эх сурвалж

- Render Blueprint: https://render.com/docs/blueprint-spec
- Render Free instance: https://render.com/docs/free
- Neon pricing: https://neon.com/pricing
- GHG Protocol Scope 2: https://ghgprotocol.org/scope-2-guidance
- GHG Protocol standard development update: https://ghgprotocol.org/blog/ghg-protocol-announces-key-standard-development-updates
- GRI 102: Climate Change 2025: https://www.globalreporting.org/publications/documents/english/gri-102-climate-change-2025/
