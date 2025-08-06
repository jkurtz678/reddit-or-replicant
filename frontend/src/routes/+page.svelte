<script lang="ts">
	import { onMount } from 'svelte';

	let redditData: any = null;
	let loading = true;
	let error = '';

	onMount(async () => {
		try {
			const response = await fetch('/api/test-reddit');
			if (!response.ok) throw new Error('Failed to fetch');
			redditData = await response.json();
		} catch (err) {
			error = 'Failed to load Reddit data';
			console.error(err);
		} finally {
			loading = false;
		}
	});

	function renderComment(comment: any, depth = 0): any {
		if (!comment || !comment.data) return null;
		
		const replies = comment.data.replies && typeof comment.data.replies === 'object' && comment.data.replies.data?.children
			? comment.data.replies.data.children
				.filter((child: any) => child.kind === 't1')
				.map((reply: any) => renderComment(reply, depth + 1))
				.filter(Boolean)
			: [];

		return {
			...comment.data,
			depth,
			replies
		};
	}

	function getCommentsTree(comments: any[]) {
		if (!comments) return [];
		return comments
			.filter(comment => comment.kind === 't1')
			.map(comment => renderComment(comment, 0))
			.filter(Boolean);
	}

	function getAllComments(comment: any, allComments: any[] = []): any[] {
		if (!comment) return allComments;
		
		allComments.push(comment);
		if (comment.replies && comment.replies.length > 0) {
			comment.replies.forEach((reply: any) => {
				getAllComments(reply, allComments);
			});
		}
		return allComments;
	}

	function decodeHtml(html: string): string {
		const txt = document.createElement('textarea');
		txt.innerHTML = html;
		return txt.value;
	}
</script>

{#if loading}
	<div class="p-8">
		<div class="animate-pulse">Loading Reddit data...</div>
	</div>
{:else if error}
	<div class="p-8 text-red-600">
		{error}
	</div>
{:else if redditData}
	<div class="max-w-4xl mx-auto bg-white">
		<!-- Post (first listing) -->
		{#if redditData[0]?.kind === 'Listing' && redditData[0].data.children}
			{#each redditData[0].data.children as item}
				{#if item.kind === 't3'}
					<div class="border-b border-gray-200 p-6">
						<div class="mb-4">
							<span class="text-sm text-gray-500">r/{item.data.subreddit}</span>
							<span class="text-sm text-gray-400 ml-2">• Posted by u/{item.data.author}</span>
						</div>
						<h1 class="text-2xl font-bold mb-4">{item.data.title}</h1>
						{#if item.data.selftext}
							<div class="text-gray-800 mb-4 whitespace-pre-wrap">{item.data.selftext}</div>
						{/if}
						<div class="text-sm text-gray-500">
							{item.data.score} points • {item.data.num_comments} comments
						</div>
					</div>
				{/if}
			{/each}
		{/if}

		<!-- Comments (second listing) -->
		{#if redditData[1]?.kind === 'Listing' && redditData[1].data.children}
			<div class="p-6">
				<h2 class="text-lg font-semibold mb-4">Comments</h2>
				{#each getCommentsTree(redditData[1].data.children) as comment}
					{@const allComments = getAllComments(comment)}
					{#each allComments as flatComment}
						<div class="comment mb-4" style="margin-left: {flatComment.depth * 20}px">
							<div class="border-l-2 border-gray-200 pl-4">
								<div class="text-sm text-gray-600 mb-2">
									<span class="font-medium">u/{flatComment.author}</span>
									<span class="ml-2">{flatComment.score} points</span>
								</div>
								<div class="text-gray-800 mb-3">{@html decodeHtml(flatComment.body_html)}</div>
							</div>
						</div>
					{/each}
				{/each}
			</div>
		{/if}
	</div>
{/if}
