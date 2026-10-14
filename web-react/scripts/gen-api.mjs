// Generate the UI's API types from the backend's OpenAPI contract (#458): `yarn gen:api`.
//
// Reads ../openapi.json (written by scripts/export_openapi.py) and writes
// src/core/types/generated/openapi.ts. CI reruns this and fails when the committed file differs.
//
// `defaultNonNullable: false` keeps a property with a default optional unless the schema lists it
// as required: request fields the server defaults (e.g. `admin_override`) stay optional.
import fs from "node:fs";
import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";

const schema = new URL("../../openapi.json", import.meta.url);
const output = new URL("../src/core/types/generated/openapi.ts", import.meta.url);

const ast = await openapiTS(schema, { defaultNonNullable: false });
fs.mkdirSync(new URL(".", output), { recursive: true });
fs.writeFileSync(output, `${COMMENT_HEADER}${astToString(ast)}`, "utf8");
console.log(`wrote ${output.pathname}`);
