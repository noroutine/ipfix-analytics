<script>
	import '@evidence-dev/tailwind/fonts.css';
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;
</script>

<EvidenceDefaultLayout {data} hideSidebar=true hideHeader=true title="IPFIX Analytics" neverShowQueries=true hideBreadcrumbs=true builtWithEvidence=false>
	<slot slot="content" />
</EvidenceDefaultLayout>
