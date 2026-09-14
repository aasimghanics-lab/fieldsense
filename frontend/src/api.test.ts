import { describe, it, expect, vi, afterEach } from 'vitest';
import { api, queryString } from './api';
afterEach(()=>vi.unstubAllGlobals());
describe('research API client',()=>{
  it('omits empty filters and escapes identifiers',()=>expect(queryString({field:'A & B',sensor:''})).toBe('field=A+%26+B'));
  it('surfaces a useful storage failure',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,json:async()=>({detail:'Research storage is temporarily unavailable.'})}));await expect(api('/readings')).rejects.toThrow('Research storage');});
  it('returns real server data',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({total:42})}));expect(await api('/readings')).toEqual({total:42});});
});
