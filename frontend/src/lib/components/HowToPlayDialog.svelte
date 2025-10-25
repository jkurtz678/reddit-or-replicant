<script lang="ts">
	import { fade, scale } from 'svelte/transition';

	export let isOpen = false;
	export let onClose: () => void;

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			onClose();
		}
	}
</script>

{#if isOpen}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center p-4"
		style="background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(4px);"
		on:click={handleBackdropClick}
		on:keydown={(e) => e.key === 'Escape' && onClose()}
		role="button"
		tabindex="-1"
		transition:fade={{ duration: 200 }}
	>
		<div
			class="max-w-2xl w-full border border-gray-700 rounded-lg p-8 relative"
			style="background: rgba(17, 17, 20, 0.98);"
			transition:scale={{ duration: 200, start: 0.95 }}
		>
			<!-- Close button -->
			<button
				on:click={onClose}
				class="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors text-2xl leading-none"
				aria-label="Close dialog"
			>
				×
			</button>

			<!-- Header -->
			<div class="mb-6">
				<h2
					class="text-2xl font-bold mb-4"
					style="color: #00d4ff; text-shadow: 0 0 10px rgba(0, 212, 255, 0.3);"
				>
					How to Play
				</h2>
			</div>

			<!-- Content -->
			<div class="space-y-6 text-gray-200">
				<div>
					<p class="leading-relaxed">
						The post below is real, pulled directly from Reddit — but it's been infiltrated by <span
							class="font-bold text-red-500"
							style="text-shadow: 0 0 10px rgba(239, 68, 68, 0.8), 0 0 20px rgba(239, 68, 68, 0.6);"
							>Replicants</span
						>.
					</p>
					<p class="leading-relaxed mt-4">
						Your goal: identify which comments are AI-generated (Replicant) and which are actually human (Reddit).
					</p>
				</div>

				<div>
					<p class="leading-relaxed">
						<span class="font-semibold" style="color: #ef4444; text-shadow: 0 0 10px rgba(239, 68, 68, 0.8), 0 0 20px rgba(239, 68, 68, 0.6);">The Tyrell Directive:</span> Some Replicants are pushing a coordinated agenda to manipulate the discussion. Spotting this pattern can help you identify them.
					</p>
				</div>
			</div>

			<!-- Close button at bottom -->
			<div class="mt-8 flex justify-end">
				<button
					on:click={onClose}
					class="px-8 py-3 text-white rounded transition-all duration-200 hover:scale-105 font-semibold cursor-pointer"
					style="background: linear-gradient(135deg, #7f1d1d, #ef4444); border: 1px solid #ef4444; box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);"
					on:mouseenter={(e) =>
						(e.currentTarget.style.boxShadow = '0 0 20px rgba(239, 68, 68, 0.4)')}
					on:mouseleave={(e) =>
						(e.currentTarget.style.boxShadow = '0 0 10px rgba(239, 68, 68, 0.2)')}
				>
					Continue
				</button>
			</div>
		</div>
	</div>
{/if}
