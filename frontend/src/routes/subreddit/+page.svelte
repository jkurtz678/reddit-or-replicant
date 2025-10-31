<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import { databaseManager } from '$lib/environment';

	let contentVisible = false;
	let stats: { global: { accuracy_percentage: number; total_guesses: number } } | null = null;
	let statsLoading = true;

	onMount(async () => {
		// Trigger fade-in animation
		setTimeout(() => {
			contentVisible = true;
		}, 100);

		// Fetch stats
		try {
			const response = await fetch(`${databaseManager.getApiUrl()}/api/stats`, {
				headers: databaseManager.getHeaders()
			});
			if (response.ok) {
				stats = await response.json();
			}
		} catch (error) {
			console.error('Failed to fetch stats:', error);
		} finally {
			statsLoading = false;
		}
	});

	// Hardcoded subreddits with descriptions
	const subreddits = [
		{
			name: 'news',
			display: 'r/news',
			description: 'Breaking news and current events from around the world.'
		},
		{
			name: 'unpopularopinion',
			display: 'r/unpopularopinion',
			description: 'Controversial takes and unconventional perspectives.'
		},
		{
			name: 'changemyview',
			display: 'r/changemyview',
			description: "Discussions aimed at changing people's minds."
		}
	];

	function selectSubreddit(subredditName: string) {
		goto(`/subreddit/${subredditName}`);
	}
</script>

<svelte:head>
	<title>Reddit or Replicant</title>
</svelte:head>

<div class="min-h-screen text-gray-100 relative z-10">
	<!-- Fixed Toolbar -->
	<div
		class="fixed top-0 left-0 right-0 z-50 border-b border-gray-700"
		style="background: rgba(17, 17, 20, 0.95); backdrop-filter: blur(10px);"
	>
		<div class="max-w-5xl mx-auto px-8 xl:px-0 py-3">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-4">
					<a href="/" class="transition-colors flex items-center gap-1" style="color: #00d4ff;" on:mouseenter={(e) => e.target.style.color='#33e0ff'} on:mouseleave={(e) => e.target.style.color='#00d4ff'}>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round">
							<line x1="19" y1="12" x2="5" y2="12"></line>
							<polyline points="12 19 5 12 12 5"></polyline>
						</svg>
						Back
					</a>
					<h1 class="text-lg font-bold hidden sm:block" style="color: #f3f4f6; text-shadow: 0 0 8px rgba(0, 212, 255, 0.1);">
						Reddit or <span class="glitch" data-text="Replicant">Replicant</span>?
					</h1>
				</div>
				<div class="flex items-center gap-4">
					<a href="/about" class="transition-colors text-sm" style="color: #00d4ff;"> About </a>
				</div>
			</div>
		</div>
	</div>

	<!-- Content with top padding to account for fixed toolbar -->
	<div class="pt-16">
		{#if contentVisible}
			<div class="container mx-auto p-8 xl:px-0" transition:fade={{ duration: 1000 }}>
				<div class="max-w-6xl mx-auto">
					<!-- Header -->
					<div class="text-center mb-12">
						<!-- Tyrell Corporation Banner -->
						<div class="mb-8 sm:mb-12 sm:mt-4">
							<h1
								class="text-2xl sm:text-3xl font-bold text-white mb-6"
								style="text-shadow: 0 0 15px rgba(255, 255, 255, 0.4), 0 0 30px rgba(173, 216, 230, 0.2);"
							>
								The Tyrell Corporation's infiltration has begun
							</h1>
							<p
								class="text-gray-300 text-lg max-w-4xl mx-auto leading-relaxed"
								style="text-shadow: 0 0 8px rgba(255, 255, 255, 0.1);"
							>
								Human-passing robots called <span
									class="font-bold text-red-500"
									style="text-shadow: 0 0 10px rgba(239, 68, 68, 0.8), 0 0 20px rgba(239, 68, 68, 0.6), 0 0 30px rgba(220, 38, 38, 0.4);"
									>Replicants</span
								> are now embedded within these communities
							</p>
							<p
								class="text-gray-300 text-lg max-w-4xl mx-auto leading-relaxed mt-4"
								style="text-shadow: 0 0 8px rgba(255, 255, 255, 0.1);"
							>
								See if you can separate human from AI
							</p>
						</div>
					</div>

					<!-- Subreddit Cards -->
					<div class="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
						{#each subreddits as subreddit}
							<div
								class="border border-gray-700 rounded-lg p-8 cursor-pointer transition-all duration-200 hover:border-blue-400 hover:scale-105"
								style="background: rgba(17, 17, 20, 0.85); backdrop-filter: blur(10px);"
								on:click={() => selectSubreddit(subreddit.name)}
								on:keydown={(e) => e.key === 'Enter' && selectSubreddit(subreddit.name)}
								role="button"
								tabindex="0"
							>
								<div class="text-center">
									<h3
										class="text-xl font-semibold mb-4"
										style="color: #00d4ff; text-shadow: 0 0 8px rgba(0, 212, 255, 0.2);"
									>
										{subreddit.display}
									</h3>
									<p class="text-gray-300 leading-relaxed content-text">
										{subreddit.description}
									</p>
									<div class="mt-6">
										<button
											class="px-6 py-2 text-white rounded transition-all duration-200 hover:scale-105 cursor-pointer"
											style="background: linear-gradient(135deg, #7f1d1d, #ef4444); border: 1px solid #ef4444; box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);"
											on:mouseenter={(e) =>
												(e.target.style.boxShadow = '0 0 20px rgba(239, 68, 68, 0.4)')}
											on:mouseleave={(e) => (e.target.style.boxShadow = '0 0 10px rgba(239, 68, 68, 0.2)')}
										>
											Enter Community
										</button>
									</div>
								</div>
							</div>
						{/each}
					</div>

					<!-- Global Stats Section -->
					{#if !statsLoading && stats && stats.global.total_guesses > 0}
						<div class="mt-16 max-w-3xl mx-auto text-center" transition:fade={{ duration: 1000, delay: 300 }}>
							<p class="text-lg leading-relaxed text-gray-300 mb-2">
								Replicants are only detected <span
									class="font-bold text-red-500 text-2xl"
									style="text-shadow: 0 0 10px rgba(239, 68, 68, 0.8), 0 0 20px rgba(239, 68, 68, 0.6);"
									>{stats.global.replicant_detection_rate}%</span
								> of the time
							</p>
							<p class="text-lg leading-relaxed text-gray-300">
								The rest remain hidden, distorting our social media communities
							</p>
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</div>
</div>
