# CARBON ESG — Demo ба pilot runbook

**Шинэчилсэн огноо:** 2026-11-09  
**Төлөв:** Scope 1/2 MVP интеграцлагдсан; production approval биш. Factor geography/applicability өргөтгөл PR #58-д хүлээгдэж байгаа тул merge + migration + staging validation дуусах хүртэл шинэ талбаруудыг production-д ашиглахгүй.

## 1. Одоогийн бодит боломж

main салбарын код дараах үндсэн урсгалтай:

- Neon Managed Auth sign-up/sign-in, FastAPI дээр EdDSA JWT шалгалт.
- Байгууллага үүсгэх, тухайн хэрэглэгчийн байгууллагуудыг жагсаах.
- PostgreSQL tenant schema, transaction-local RLS context, tenant тусгаарлах composite foreign key.
- Тайлант inventory үүсгэх, жагсаах; Scope 2-ын үндсэн тайлагналын аргыг сонгох.
- Emission factor бүртгэх, эх сурвалж/он/нэгж/хувилбар хадгалах, хараат бус owner/admin review.
- Activity record нэмэх, Decimal arithmetic-аар Scope 1/2 тооцох.
- Scope 2 location-based болон market-based дүнг тусад нь хадгалах; хоёр дүнг хооронд нь хэзээ ч нэмэхгүй.
- Immutable calculation input snapshot, audit event, CSV export.
- Evidence Vault API/UI байгаа ч private object storage + ClamAV тохиргоогүй үед upload/download fail-closed.

**Анхаарах:** GitHub код амжилттай build болсон нь Neon/Render дээр deployment, migration, auth, malware scanning бодитоор ажиллаж байгааг нотлохгүй. Production өгөгдөл бүү оруул.

## 2. Factor geography/applicability — PR #58

Энэ PR дараах шаардлагыг нэмнэ; merge хийсний дараа migration 0006_factor_geo_validity-г зөвхөн тусгаарласан Neon development branch дээр эхэлж туршина.

- Factor-д газарзүйн код, нэр, хил заагийн төрөл (global, national, subnational, grid, market, facility, other) болон valid_from/valid_to огноо бүртгэнэ.
- factor_year нь эх сурвалжийн өгөгдөл/нийтлэлийн он; хүчинтэй хугацааны оронд ашиглахгүй.
- Activity record бодит газарзүйн код/нэрээ хадгална. Factor-ийн код GLOBAL биш бол activity-ийн кодтой яг таарах ёстой.
- Factor-ийн хүчинтэй хугацаа inventory-ийн тайлант хугацааг бүхэлд нь хамрах ёстой.
- Өмнөх factor-уудын газарзүй, хүчинтэй хугацаа тодорхойгүй бол LEGACY_UNSPECIFIED болон NULL хэвээр үлдээнэ. Тэдгээрийг шинэ activity болон дахин тооцоололд ашиглахгүй; factor_year-ээс validity-г таамаглахгүй.

## 3. Архитектур ба тохиргоо

- Web: Next.js Node runtime.
- API: FastAPI.
- DB: Neon PostgreSQL; migration credential болон runtime restricted role тусдаа.
- Auth: Neon Managed Auth JWT; cookie secret зөвхөн server-side environment variable.
- Hosting: Render Blueprint preview боломжтой. Free tier sleep/cold-start болон provider limits-тэй; deployment хийх өдөр албан ёсны үнэ/хязгаарыг шалга.

Environment variable нэрсийг apps/api/.env.example, apps/web/.env.example, render.yaml-аас ав. Нууц утгыг GitHub-д хэзээ ч commit хийхгүй.

## 4. Local development

### API

~~~bash
cd apps/api
python -m venv .venv
# virtual environment идэвхжүүл
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest -q
~~~

### Web

~~~bash
cd apps/web
cp .env.example .env.local
# Neon Auth болон NEXT_PUBLIC_API_URL-ийг local/dev утгаар тохируул
npm install
npm run dev
npm run typecheck
npm run build
~~~

Web: http://localhost:3000; API: http://localhost:8000.

## 5. Demo урсгал

1. Туршилтын хэрэглэгчээр sign-up/sign-in хийнэ.
2. Байгууллага үүсгэнэ.
3. Тайлант хугацаа, Scope 2 primary method сонгон inventory үүсгэнэ.
4. Зөвхөн эх сурвалж дээрх утгыг factor болгон бүртгэнэ. Утга, нэгж, эх сурвалжийн HTTPS URL, баримт бичиг, factor year, version-ийг шалгана.
5. Factor geography PR merge + migration хийсний дараа газарзүйн код/нэр, boundary, хүчинтэй огноог эх сурвалжаас баталгаажуулж бүртгэнэ.
6. Өөр owner/admin factor-ийг review note-тойгоор approve/reject хийнэ. Submitter өөрийн factor-ийг батлах ёсгүй.
7. Inventory-ийн бүх хугацаанд хүчинтэй, activity geography-тэй тохирох approved factor сонгож activity record оруулна.
8. Scope 1, Scope 2 location-based, Scope 2 market-based дүнг тус тусад нь харуулж, calculation snapshot болон CSV provenance-г шалгана.

Хэрэв баталгаажсан factor байхгүй бол тоо зохиож үзүүлэхгүй. AI-аар гаргасан factor value-г authoritative calculator-ийн оролт болгохгүй.

## 6. Demo үед заавал хэлэх хязгаарлалт

- Scope 3 бүрэн хэрэгжээгүй.
- Одоогийн факторын calculator нь CO2e суурьтай. GRI 102: Climate Change 2025-ийн CO2/CH4/N2O gas-level breakdown, biogenic emissions, latest IPCC GWP-100 conversion, base-year, өмнөх хоёр тайлант хугацааны харьцуулалт бүрэн хэрэгжээгүй.
- Scope 2-ын хоёр аргыг тусад нь тооцдог боловч market-based contractual instrument-ийн бүх чанарын шалгуур, supplier-specific/residual-mix evidence бүрэн автоматжаагүй.
- Source review нь хүний хяналт; geography metadata оруулсан нь тухайн factor-ийн шинжлэх ухааны тохиромжтойг автоматаар батлахгүй.
- Evidence storage, malware scan, backup/restore, retention, monitoring баталгаажаагүй.
- GRI/IFRS/GHG Protocol conformity, independent assurance, Монголын зохицуулалтын бүрэн нийцэл гэж сурталчлахгүй.

## 7. Go-live gate

- PR #58 merge болсон эсэх, main-ийн migration head 0006_factor_geo_validity мөн эсэхийг шалгах.
- Тусгаарласан Neon development branch дээр alembic upgrade head, alembic current ажиллуулах.
- Runtime DB role NOSUPERUSER, NOBYPASSRLS, table owner биш гэдгийг шалгах.
- Хоёр өөр хэрэглэгч/байгууллагаар cross-tenant read/write тест хийх.
- Signup → organization → inventory → factor submit → independent review → activity → calculation → audit урсгалыг staging дээр бүрэн шалгах.
- Factor-ийн geography code match, factor validity covers full inventory period, legacy NULL validity factor reject болохыг турших.
- Scope 2 location/market totals тусдаа үлдэхийг батлах.
- Auth trusted origin, cookie/session expiry, sign-out, iOS Safari behavior шалгах.
- Evidence storage + ClamAV, private download URL, backup/restore, rate limiting, monitoring, incident response, data retention шийдэх.
- Монголын хууль, стандартын хүчин төгөлдөр байдал болон тайлангийн аргачлалыг мэргэжлийн хүнээр хянуулах.

## 8. Аюулгүй demo data

- Synthetic байгууллага, хэрэглэгч, activity data ашигла.
- Бодит хэрэглэгчийн мэдээлэл, банк/гэрээний баримт, нууц үг, token, database URL бүү оруул.
- Албан ёсны эх сурвалжгүй factor зохиож seed хийхгүй.
- Demo calculation-ийг баталгаажсан тайлан эсвэл assurance statement гэж нэрлэхгүй.

## 9. Үнэгүй орчны нөхцөл

Render/Neon free tier нь sleep, compute, storage, connection болон usage хязгаартай байж болно. Paid resource автоматаар үүсгэхгүй. Custom domain худалдан авах шаардлагагүй.

## 10. Албан ёсны эх сурвалж

- Render Blueprint: https://render.com/docs/blueprint-spec
- Render Free instance: https://render.com/docs/free
- Neon pricing: https://neon.com/pricing
- GHG Protocol calculation guidance: https://ghgprotocol.org/calculation-tools-faq
- GHG Protocol Scope 2: https://ghgprotocol.org/scope-2-guidance
- GRI 102: Climate Change 2025: https://www.globalreporting.org/publications/documents/english/gri-102-climate-change-2025/
- GRI Climate Change and Energy standards: https://www.globalreporting.org/standards/standards-development/topic-standard-for-climate-change-and-energy/
