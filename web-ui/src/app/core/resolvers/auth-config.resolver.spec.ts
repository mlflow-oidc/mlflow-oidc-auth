import { firstValueFrom, of } from 'rxjs';
import { AuthConfigResolver } from './auth-config.resolver';
import { RuntimeConfigService } from '../services/runtime-config.service';
import { RuntimeConfig } from '../models/runtime-config.interface';

// filepath: /Users/alexander_kharkevich/Documents/projects/mlflow-oidc/mlflow-oidc-user-management/web-ui/src/app/core/resolvers/auth-config.resolver.spec.ts

describe('AuthConfigResolver', () => {
    // ensure getCurrentConfig is a jest.Mock so mockReturnValue is available on it
    let mockRuntimeConfigService: { getCurrentConfig: jest.Mock };
    let resolver: AuthConfigResolver;

    const sampleConfig = ({ authEnabled: true, issuer: 'https://example.com' } as unknown) as RuntimeConfig;

    beforeEach(() => {
        mockRuntimeConfigService = {
            getCurrentConfig: jest.fn()
        };
        // cast via unknown because the mock object doesn't strictly match the full service type
        resolver = new AuthConfigResolver(mockRuntimeConfigService as unknown as RuntimeConfigService);
        jest.clearAllMocks();
    });

    it('should be created', () => {
        expect(resolver).toBeTruthy();
    });

    it('resolve should return an Observable<RuntimeConfig> when service returns an observable', async () => {
        mockRuntimeConfigService.getCurrentConfig!.mockReturnValue(of(sampleConfig));

        const result = resolver.resolve();

        // await the observable value to ensure it resolves correctly
        const value = await firstValueFrom(result as any);
        expect(value).toEqual(sampleConfig);
        expect(mockRuntimeConfigService.getCurrentConfig).toHaveBeenCalledTimes(1);
    });

    it('resolve should return a Promise<RuntimeConfig> when service returns a promise', async () => {
        mockRuntimeConfigService.getCurrentConfig!.mockReturnValue(Promise.resolve(sampleConfig));

        const result = resolver.resolve();

        await expect(result).resolves.toEqual(sampleConfig);
        expect(mockRuntimeConfigService.getCurrentConfig).toHaveBeenCalledTimes(1);
    });

    it('resolve should return RuntimeConfig directly when service returns a value', () => {
        mockRuntimeConfigService.getCurrentConfig!.mockReturnValue(sampleConfig);

        const result = resolver.resolve();

        expect(result).toBe(sampleConfig);
        expect(mockRuntimeConfigService.getCurrentConfig).toHaveBeenCalledTimes(1);
    });

    it('should delegate to runtimeConfigService.getCurrentConfig and not alter the returned value', async () => {
        // ensure delegation for observable
        mockRuntimeConfigService.getCurrentConfig!.mockReturnValue(of(sampleConfig));
        const obsResult = resolver.resolve();
        const obsValue = await firstValueFrom(obsResult as any);
        expect(obsValue).toEqual(sampleConfig);

        // ensure delegation for promise
        mockRuntimeConfigService.getCurrentConfig!.mockReturnValue(Promise.resolve(sampleConfig));
        const promiseResult = resolver.resolve();
        await expect(promiseResult).resolves.toEqual(sampleConfig);

        // ensure delegation for direct value
        mockRuntimeConfigService.getCurrentConfig!.mockReturnValue(sampleConfig);
        const directResult = resolver.resolve();
        expect(directResult).toBe(sampleConfig);

        expect(mockRuntimeConfigService.getCurrentConfig).toHaveBeenCalledTimes(3);
    });
});
