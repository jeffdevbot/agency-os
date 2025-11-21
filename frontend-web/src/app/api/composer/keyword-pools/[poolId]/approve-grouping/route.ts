import { NextRequest, NextResponse } from 'next/server';
import { createSupabaseRouteClient } from '@/lib/supabase/serverClient';
import { resolveComposerOrgIdFromSession } from '@/lib/composer/serverUtils';
import { mapRowToPool } from '../route';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ poolId: string }> }
) {
  try {
    const { poolId } = await params;
    const supabase = await createSupabaseRouteClient();

    // Get current session
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const organizationId = resolveComposerOrgIdFromSession(session);

    if (!organizationId) {
      return NextResponse.json(
        { error: 'Organization not found in session' },
        { status: 403 },
      );
    }

    // Fetch the pool with its current updated_at timestamp for optimistic locking
    const { data: pool, error: poolError } = await supabase
      .from('composer_keyword_pools')
      .select('*')
      .eq('id', poolId)
      .eq('organization_id', organizationId)
      .single();

    if (poolError || !pool) {
      return NextResponse.json({ error: 'Pool not found' }, { status: 404 });
    }

    // Validate that the pool is in the correct state
    if (pool.status !== 'cleaned') {
      return NextResponse.json(
        {
          error: `Pool must be in 'cleaned' status to approve grouping. Current status: ${pool.status}`,
        },
        { status: 400 }
      );
    }

    // Validate that there are cleaned keywords
    const cleanedKeywords = (pool.cleaned_keywords as string[]) || [];
    if (cleanedKeywords.length === 0) {
      return NextResponse.json(
        { error: 'Cannot approve grouping: No cleaned keywords in pool' },
        { status: 400 }
      );
    }

    // Validate that grouping config exists
    if (!pool.grouping_config || !pool.grouping_config.basis) {
      return NextResponse.json(
        { error: 'Cannot approve grouping: No grouping plan configured' },
        { status: 400 }
      );
    }

    // Update pool status with optimistic locking
    // This prevents race conditions by ensuring the pool hasn't been modified
    // since we read it (checking that updated_at hasn't changed)
    const { data: updatedPool, error: updateError } = await supabase
      .from('composer_keyword_pools')
      .update({
        status: 'grouped',
        approved_at: new Date().toISOString(),
        grouped_at: new Date().toISOString(),
      })
      .eq('id', poolId)
      .eq('updated_at', pool.updated_at) // Optimistic locking check
      .select()
      .single();

    // Check if update failed due to concurrent modification
    if (updateError) {
      if (updateError.code === 'PGRST116') {
        // No rows returned - means updated_at changed (concurrent modification)
        return NextResponse.json(
          {
            error: 'Pool was modified by another user. Please refresh and try again.',
          },
          { status: 409 } // Conflict
        );
      }
      throw updateError;
    }

    if (!updatedPool) {
      // No rows were updated - concurrent modification occurred
      return NextResponse.json(
        {
          error: 'Pool was modified by another user. Please refresh and try again.',
        },
        { status: 409 } // Conflict
      );
    }

    return NextResponse.json({
      pool: mapRowToPool(updatedPool),
    });
  } catch (error) {
    console.error('Error approving grouping:', error);
    return NextResponse.json(
      {
        error:
          error instanceof Error ? error.message : 'Failed to approve grouping',
      },
      { status: 500 }
    );
  }
}
