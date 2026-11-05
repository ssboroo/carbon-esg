# CARBON ESG

Монголд төвлөрсөн ESG болон хүлэмжийн хийн бүртгэлийн SaaS платформ.

## Архитектур

- \`apps/web\`: Next.js + TypeScript frontend
- \`apps/api\`: Python FastAPI backend
- Нэвтрэлт: Neon Managed Better Auth (email/password), Next.js same-origin proxy; FastAPI нь Neon JWKS ашиглан EdDSA JWT-г шалгана.
- PostgreSQL multi-tenant өгөгдлийн загвар, Alembic migration, tenant-scoped composite foreign key болон Row-Level Security (RLS).
- Ялгарлыг activity data × баримтжуулсан emission factor аргаар детерминист тооцно.
- AI нь баримт бичиг унших, тайлбар/тайлангийн ноорог гаргахад тусалж болох ч emission factor болон албан ёсны тооцооны үр дүнг зохиохгүй.

## API

API-г \`apps/api\` хавтаснаас ажиллуулна.

\`\`\`bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
\`\`\`

| Method | Endpoint | Тайлбар |
|---|---|---|
| GET | \`/health\` | Үйлчилгээний төлөв |
| GET | \`/v1/auth/me\` | JWT баталгаажуулалт |
| GET / POST | \`/v1/organizations\` | Байгууллага жагсаах / үүсгэх |
| GET | \`/v1/organizations/{organization_id}/emission-factors\` | Тухайн байгууллагын баталгаажсан коэффициентүүд |
| GET / POST | \`/v1/organizations/{organization_id}/inventories\` | Тайлант бүртгэл жагсаах / үүсгэх |
| GET / POST | \`/v1/organizations/{organization_id}/inventories/{inventory_id}/activities\` | Үйл ажиллагааны мөр харах / нэмэх |
| POST | \`/v1/organizations/{organization_id}/inventories/{inventory_id}/calculate\` | Scope 1/2 тооцоог snapshot болгон хадгалах |
| GET | \`/v1/organizations/{organization_id}/inventories/{inventory_id}/calculations\` | Тооцооллын түүх |
| POST | \`/v1/calculations\` | Explicit factor ашигласан stateless preview; байгууллагын тайлан биш |
| GET | \`/docs\` | API баримтжуулалт |

Байгууллагын өгөгдлийн endpoint бүр Neon JWT шаарддаг. Хэрэглэгч тухайн байгууллагын membership-тэй байх ёстой; өгөгдөл уншихад viewer эрх зөвшөөрөгдөх ба бичих/тооцоолох үйлдэлд owner, admin эсвэл editor эрх шаардлагатай. PostgreSQL RLS context-ийг transaction бүрд эхлээд verified identity, дараа нь membership баталгаажсаны дараа organization ID-аар тохируулна.

## Тооцооллын бүрэн бүтэн байдал

Persisted inventory API нь activity хүсэлтээс emission-factor утга хүлээн авахгүй. Харин тухайн байгууллагад бүртгэлтэй, \`verified=true\` коэффициентийг серверээс сонгож, Scope, category, CO2e basis болон нэгжийг тулгана. Нэгжийн тэмдэглэгээ яг ижил байх ёстой. Үр дүнг Decimal арифметикаар kgCO2e-д тооцож, ROUND_HALF_UP аргаар 8 орны нарийвчлалд хадгална.

Activity record нь коэффициентийн утга/нэгжийн snapshot агуулна. Calculation run нь methodology version болон activity, factor, эх сурвалж, он, хувилбарын provenance snapshot хадгална. Inventory үүсгэх, activity нэмэх, тооцоолох бүрт audit event үүснэ.

**Коэффициентийн сан хоосон эхэлнэ.** Hard-coded эсвэл зохиомол emission factor байхгүй. Коэффициентийг албан ёсны/найдвартай эх сурвалжаас баримтжуулж, эх сурвалжийн HTTPS URL, баримтын нэр, он, хувилбарыг бүртгэн, эрх бүхий data steward хянаж баталгаажуулсны дараа л \`verified=true\` болгоно. Одоогийн API-д коэффициент үүсгэх/батлах admin endpoint хараахан байхгүй; энэ нь дараагийн ажлын нэг.

Stateless \`POST /v1/calculations\` нь клиентээс explicit factor авдаг анхны preview endpoint хэвээр. Production байгууллагын тайланг persisted inventory workflow-оор гаргана.

## PostgreSQL ба нэвтрэлт

Runtime-д Neon's pooled connection string-ийг \`DATABASE_URL\`, migration-д direct (non-pooler) connection string-ийг \`DATABASE_URL_UNPOOLED\` болгон тохируулна. Нууц утгыг repository-д commit хийхгүй. API runtime-д \`neondb_owner\` зэрэг superuser/BYPASSRLS эрхтэй role ашиглахгүй; зөвхөн шаардлагатай schema/table-д хязгаарласан role ашиглана.

\`NEON_AUTH_BASE_URL\`, \`NEON_AUTH_COOKIE_SECRET\` нь web service-д; \`NEON_AUTH_BASE_URL\`, \`NEON_AUTH_JWKS_URL\` нь FastAPI-д шаардлагатай. Cookie secret дор хаяж 32 тэмдэгт байх ёстой бөгөөд зөвхөн server-side environment variable байна.

Migration-ийг эхлээд disposable Neon development branch дээр туршина:

\`\`\`bash
cd apps/api
alembic upgrade head
\`\`\`

Tenant schema-г shared Neon main branch дээр шууд ажиллуулахгүй. Deployment тохиргоо болон free-first хувилбарын зааврыг [DEPLOYMENT.md](DEPLOYMENT.md)-оос үзнэ үү.

## Local development

### API

\`\`\`bash
cd apps/api
python -m venv .venv
# virtual environment-ээ идэвхжүүлээд:
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
pytest -q
\`\`\`

### Web

\`\`\`bash
cd apps/web
npm install
npm run dev
\`\`\`

## Нягтлан бодох бүртгэлийн аргачлал ба хязгаарлалт

Суурь аргачлал нь GHG Protocol-ийн activity data × documented emission factor зарчимд тулгуурлана. Production тайланд Монголын тухайн он/салбарт тохирох хүчин зүйл, байгууллагын болон үйл ажиллагааны хил хязгаар, өгөгдлийн чанарын шалгалт, хүний хяналт шаардлагатай.

Одоогоор Scope 2 market-based/location-based ялгалт, factor approval/admin UI/API, factor library-ийн албан ёсны Монгол өгөгдөл, activity correction workflow, PDF/Excel экспорт болон Scope 3 бүрэн хэрэгжээгүй.

Эх сурвалж:
- [GHG Protocol — How do I calculate emissions?](https://ghgptechassistance.zendesk.com/hc/en-us/articles/37790958151700-How-do-I-calculate-emissions)
- [GHG Protocol — Standards and Guidance](https://ghgprotocol.org/standards-guidance)

## MVP дараалал

1. Нэвтрэлт ба байгууллагын workspace
2. Тайлант inventory, activity data persistence, tenant isolation
3. Монголд хамаарах баталгаажсан emission-factor library
4. Scope 1/2 calculation, аргачлалын сонголт, аудитын snapshot
5. Хүний review workflow, PDF/Excel экспорт
6. Scope 3 болон өргөтгөсөн ESG disclosure
