import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ poolId: string }> }
) {
  try {
    const { poolId } = await params;
    const supabase = await createClient();

    // Get current user
    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser();

    if (userError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Fetch the pool with its current updated_at timestamp for optimistic locking
    const { data: pool, error: poolError } = await supabase
      .from('composer_keyword_pools')
      .select('*, keywords:composer_keywords(*), groups:composer_keyword_groups(*)')
      .eq('id', poolId)
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

    // Validate that there are keywords
    if (!pool.keywords || pool.keywords.length === 0) {
      return NextResponse.json(
        { error: 'Cannot approve grouping: No keywords in pool' },
        { status: 400 }
      );
    }

    // Validate that there are groups
    if (!pool.groups || pool.groups.length === 0) {
      return NextResponse.json(
        { error: 'Cannot approve grouping: No groups created' },
        { status: 400 }
      );
    }

    // Validate that all keywords are assigned to groups
    const unassignedKeywords = pool.keywords.filter(
      (k: any) => !k.assigned_group_id
    );
    if (unassignedKeywords.length > 0) {
      return NextResponse.json(
        {
          error: `Cannot approve grouping: ${unassignedKeywords.length} keyword(s) not assigned to any group`,
        },
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
      success: true,
      pool: updatedPool,
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
