<script>
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;
</script>

<EvidenceDefaultLayout {data} hideSidebar=true title="IPFIX Analytics" neverShowQueries=true hideBreadcrumbs=true githubRepo="https://codeberg.org/noroutine/ipfix-analytics">
	<slot slot="content" />
</EvidenceDefaultLayout>
