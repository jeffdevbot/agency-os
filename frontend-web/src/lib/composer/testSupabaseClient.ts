import { vi } from "vitest";

type SupabaseResponse<T = any> = {
  data: T;
  error: { message: string; code?: string } | null;
  count?: number | null;
};

const createQueryBuilder = () => {
  const responseQueue: SupabaseResponse[] = [];
  const shiftResponse = (): SupabaseResponse =>
    responseQueue.length > 0 ? responseQueue.shift()! : { data: null, error: null };

  const builder: Record<string, any> = {
    select: vi.fn().mockReturnThis(),
    eq: vi.fn().mockReturnThis(),
    order: vi.fn().mockReturnThis(),
    limit: vi.fn().mockReturnThis(),
    insert: vi.fn().mockReturnThis(),
    update: vi.fn().mockReturnThis(),
    delete: vi.fn().mockReturnThis(),
    in: vi.fn().mockReturnThis(),
    single: vi.fn(() => Promise.resolve(shiftResponse())),
    maybeSingle: vi.fn(() => Promise.resolve(shiftResponse())),
    then: (onFulfilled: (value: SupabaseResponse) => unknown, onRejected?: (reason: unknown) => unknown) =>
      Promise.resolve(shiftResponse()).then(onFulfilled, onRejected),
    catch: (onRejected: (reason: unknown) => unknown) =>
      Promise.resolve(shiftResponse()).catch(onRejected),
    finally: (onFinally: () => void) => Promise.resolve(shiftResponse()).finally(onFinally),
    __pushResponse: (response: SupabaseResponse) => {
      responseQueue.push(response);
    },
  };

  return builder;
};

export const createSupabaseClientMock = () => {
  const builders: Record<string, ReturnType<typeof createQueryBuilder>> = {};
  const getBuilder = (table: string) => {
    if (!builders[table]) {
      builders[table] = createQueryBuilder();
    }
    return builders[table];
  };

  const supabase = {
    auth: {
      getSession: vi.fn(),
    },
    from: vi.fn((table: string) => getBuilder(table)),
  };

  return { supabase, builders, getBuilder };
};

export type SupabaseClientMock = ReturnType<typeof createSupabaseClientMock>;
