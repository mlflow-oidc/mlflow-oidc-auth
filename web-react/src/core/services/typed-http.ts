/**
 * Calls to the plugin's API, typed by path and method from the generated OpenAPI contract.
 *
 * `src/core/types/generated/openapi.ts` is generated from `openapi.json` (`yarn gen:api`), which
 * is exported from the backend's routers. A path, its path and query parameters, its request body
 * and its response are all checked against that contract, so a field renamed on the server is a
 * compile error here rather than a runtime bug.
 *
 * Only the types are new. Every call goes through `api-utils.ts` and `http.ts` unchanged, so the
 * runtime base path, the `X-MLFLOW-WORKSPACE` header, `credentials: "include"`, the 401 reauth
 * latch and the 204 handling all behave exactly as they do for every other call.
 */
import type { paths } from "../types/generated/openapi";
import type { QueryParams } from "../types/api";
import type { HttpResult, HttpResultWithHeaders } from "./http";
import { request, requestWithHeaders, requestWithStatus } from "./api-utils";

export type HttpMethod = "get" | "put" | "post" | "delete" | "patch";

/** Every path in the contract. */
export type ApiPath = keyof paths;

/** The paths that serve `M`. */
export type PathsWithMethod<M extends HttpMethod> = {
  [P in ApiPath]: [NonNullable<paths[P][M]>] extends [never] ? never : P;
}[ApiPath];

/** The operation `M` on `P`. */
export type ApiOperation<P extends ApiPath, M extends HttpMethod> = NonNullable<
  paths[P][M]
>;

type ParametersOf<Op> = Op extends { parameters: infer X } ? X : never;

type PathParamsOf<Op> = NonNullable<
  ParametersOf<Op> extends { path?: infer X } ? X : never
>;

type QueryParamsOf<Op> = NonNullable<
  ParametersOf<Op> extends { query?: infer X } ? X : never
>;

type JsonContent<R> = R extends { content: { "application/json": infer T } }
  ? T
  : R extends { content?: never }
    ? undefined
    : never;

type RequestBodyOf<Op> = Op extends { requestBody?: infer B }
  ? JsonContent<NonNullable<B>>
  : never;

type ResponseFor<Op, Code extends number> = Op extends {
  responses: { [K in Code]: infer R };
}
  ? JsonContent<R>
  : never;

/** The JSON body of a successful (200, 201 or 204) response to `M` on `P`. */
export type ApiResponse<P extends ApiPath, M extends HttpMethod> =
  | ResponseFor<ApiOperation<P, M>, 200>
  | ResponseFor<ApiOperation<P, M>, 201>
  | ResponseFor<ApiOperation<P, M>, 204>;

/** The JSON request body `M` on `P` takes; `never` when it takes none. */
export type ApiRequestBody<
  P extends ApiPath,
  M extends HttpMethod,
> = RequestBodyOf<ApiOperation<P, M>>;

/** A field that is required when `T` has a required member, optional when not, absent when `T` is `never`. */
type Field<K extends string, T> = [T] extends [never]
  ? { [Key in K]?: never }
  : Record<string, never> extends T
    ? { [Key in K]?: T }
    : { [Key in K]: T };

type BodyField<Op> = [RequestBodyOf<Op>] extends [never]
  ? { body?: never }
  : Op extends { requestBody: unknown }
    ? { body: RequestBodyOf<Op> }
    : { body?: RequestBodyOf<Op> };

/** Everything a call to `M` on `P` takes besides the path itself. */
export type ApiCallOptions<P extends ApiPath, M extends HttpMethod> = Field<
  "path",
  PathParamsOf<ApiOperation<P, M>>
> &
  Field<"query", QueryParamsOf<ApiOperation<P, M>>> &
  BodyField<ApiOperation<P, M>> & {
    signal?: AbortSignal;
    headers?: Record<string, string>;
  };

/** The options argument is optional exactly when nothing in it is required. */
type OptionsArg<O> =
  Record<string, never> extends Omit<O, "signal" | "headers">
    ? [options?: O]
    : [options: O];

/**
 * Substitute `{name}` placeholders in a contract path, URL-encoding each value.
 *
 * @throws Error when a placeholder has no value — a call must never reach a literal `{name}`.
 */
export function buildApiPath(
  template: string,
  params: Record<string, string | number> = {},
): string {
  return template.replace(/\{([^}]+)\}/g, (_, name: string) => {
    const value = params[name];
    if (value === undefined) {
      throw new Error(`Missing path parameter "${name}" for ${template}`);
    }
    return encodeURIComponent(String(value));
  });
}

function toRequest(
  method: HttpMethod,
  path: string,
  options: {
    path?: Record<string, string | number>;
    query?: object;
    body?: unknown;
    signal?: AbortSignal;
    headers?: Record<string, string>;
  } = {},
) {
  return {
    endpoint: buildApiPath(path, options.path),
    init: {
      method: method.toUpperCase(),
      queryParams: (options.query ?? {}) as QueryParams,
      ...(options.body !== undefined
        ? { body: JSON.stringify(options.body) }
        : {}),
      ...(options.signal ? { signal: options.signal } : {}),
      ...(options.headers ? { headers: options.headers } : {}),
    },
  };
}

/**
 * Call `method` on `path` and return the response body.
 *
 * @example
 * const user = await apiRequest("patch", "/api/2.0/mlflow/users/{username}/active", {
 *   path: { username },
 *   body: { active: false },
 * });
 */
export function apiRequest<M extends HttpMethod, P extends PathsWithMethod<M>>(
  method: M,
  path: P,
  ...[options]: OptionsArg<ApiCallOptions<P, M>>
): Promise<ApiResponse<P, M>> {
  const { endpoint, init } = toRequest(method, path, options);
  return request<ApiResponse<P, M>>(endpoint, init);
}

/** {@link apiRequest}, plus the response status. */
export function apiRequestWithStatus<
  M extends HttpMethod,
  P extends PathsWithMethod<M>,
>(
  method: M,
  path: P,
  ...[options]: OptionsArg<ApiCallOptions<P, M>>
): Promise<HttpResult<ApiResponse<P, M>>> {
  const { endpoint, init } = toRequest(method, path, options);
  return requestWithStatus<ApiResponse<P, M>>(endpoint, init);
}

/** {@link apiRequest}, plus the response status and headers (e.g. `X-Total-Count`). */
export function apiRequestWithHeaders<
  M extends HttpMethod,
  P extends PathsWithMethod<M>,
>(
  method: M,
  path: P,
  ...[options]: OptionsArg<ApiCallOptions<P, M>>
): Promise<HttpResultWithHeaders<ApiResponse<P, M>>> {
  const { endpoint, init } = toRequest(method, path, options);
  return requestWithHeaders<ApiResponse<P, M>>(endpoint, init);
}
