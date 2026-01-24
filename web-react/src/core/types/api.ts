import type {
  DynamicEndpointKey,
  StaticEndpointKey,
} from "../configs/api-endpoints";

export type QueryParams = Record<
  string,
  string | number | boolean | undefined | null
>;

type BaseFetcherConfig<T> = {
  responseType?: T;
  queryParams?: QueryParams;
  headers?: Record<string, string>;
};

export type StaticFetcherConfig<T> = BaseFetcherConfig<T> & {
  endpointKey: StaticEndpointKey;
};

export type DynamicFetcherConfig<
  T,
  K extends DynamicEndpointKey,
> = BaseFetcherConfig<T> & {
  endpointKey: K;
};
