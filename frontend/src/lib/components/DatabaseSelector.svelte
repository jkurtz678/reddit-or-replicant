<script lang="ts">
	import { databaseManager, isLocalEnvironment, type Database } from '$lib/environment';
	import { createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher<{
		change: Database;
	}>();

	let currentDatabase: Database = 'local';
	let showSelector = false;

	// Initialize and check if we should show the selector
	if (isLocalEnvironment()) {
		currentDatabase = databaseManager.get();
		showSelector = true;
	}

	function handleDatabaseChange() {
		databaseManager.set(currentDatabase);
		dispatch('change', currentDatabase);
	}
</script>

{#if showSelector}
	<div class="flex items-center gap-2">
		<span class="text-sm text-gray-400">Database:</span>
		<select
			bind:value={currentDatabase}
			on:change={handleDatabaseChange}
			class="px-2 py-1 text-sm rounded bg-gray-800 border border-gray-600 text-white focus:border-blue-400 focus:outline-none cursor-pointer"
		>
			<option value="local">Local</option>
			<option value="live">Live</option>
		</select>
	</div>
{/if}