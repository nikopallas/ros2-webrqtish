/**
 * Node Graph - D3.js force-directed graph visualization
 */
const NodeGraph = {
    svg: null,
    g: null,
    simulation: null,
    zoom: null,
    graphData: { nodes: [], edges: [] },
    autoRefreshInterval: null,

    /**
     * Initialize the node graph
     */
    init() {
        this.setupSVG();
        this.bindEvents();
        this.loadGraph();
        this.startAutoRefresh();
    },

    /**
     * Setup the SVG and D3 components
     */
    setupSVG() {
        const container = document.getElementById('graph-container');
        const width = container.clientWidth;
        const height = container.clientHeight;

        this.svg = d3.select('#graph-svg')
            .attr('width', width)
            .attr('height', height);

        // Add arrow marker definitions
        this.svg.append('defs').append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '-0 -5 10 10')
            .attr('refX', 20)
            .attr('refY', 0)
            .attr('orient', 'auto')
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .append('path')
            .attr('d', 'M 0,-5 L 10,0 L 0,5')
            .attr('class', 'edge-arrow');

        // Create main group for zoom/pan
        this.g = this.svg.append('g');

        // Setup zoom behavior
        this.zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });

        this.svg.call(this.zoom);

        // Handle resize
        window.addEventListener('resize', () => this.handleResize());
    },

    /**
     * Bind UI events
     */
    bindEvents() {
        document.getElementById('refresh-graph').addEventListener('click', () => {
            this.loadGraph();
        });

        document.getElementById('reset-zoom').addEventListener('click', () => {
            this.resetZoom();
        });

        document.getElementById('auto-refresh').addEventListener('change', (e) => {
            if (e.target.checked) {
                this.startAutoRefresh();
            } else {
                this.stopAutoRefresh();
            }
        });
    },

    /**
     * Load graph data from the API
     */
    async loadGraph() {
        try {
            this.graphData = await App.get('/graph');
            this.renderGraph();
        } catch (e) {
            console.error('Failed to load graph:', e);
        }
    },

    /**
     * Render the graph using D3 force simulation
     */
    renderGraph() {
        const container = document.getElementById('graph-container');
        const width = container.clientWidth;
        const height = container.clientHeight;

        // Clear existing elements
        this.g.selectAll('*').remove();

        // Stop existing simulation
        if (this.simulation) {
            this.simulation.stop();
        }

        const nodes = this.graphData.nodes;
        const edges = this.graphData.edges;

        // Create simulation
        this.simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(edges)
                .id(d => d.id)
                .distance(100))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(40));

        // Create edges
        const edgeGroup = this.g.append('g').attr('class', 'edges');
        const edge = edgeGroup.selectAll('line')
            .data(edges)
            .enter()
            .append('line')
            .attr('class', d => `edge type-${d.type}`)
            .attr('marker-end', 'url(#arrowhead)');

        // Create nodes
        const nodeGroup = this.g.append('g').attr('class', 'nodes');
        const node = nodeGroup.selectAll('g')
            .data(nodes)
            .enter()
            .append('g')
            .attr('class', 'node-group')
            .call(d3.drag()
                .on('start', (event, d) => this.dragStarted(event, d))
                .on('drag', (event, d) => this.dragged(event, d))
                .on('end', (event, d) => this.dragEnded(event, d)));

        // Add circles
        node.append('circle')
            .attr('r', d => d.type === 'node' ? 20 : 15)
            .attr('class', d => `node-circle type-${d.type}`)
            .on('click', (event, d) => this.showNodeInfo(d));

        // Add labels
        node.append('text')
            .attr('class', 'node-label')
            .attr('dy', d => d.type === 'node' ? 35 : 28)
            .text(d => d.label);

        // Add node type indicator
        node.append('text')
            .attr('class', 'node-label')
            .attr('dy', 4)
            .style('font-size', '10px')
            .text(d => d.type === 'node' ? 'N' : 'T');

        // Update positions on tick
        this.simulation.on('tick', () => {
            edge
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });
    },

    /**
     * Drag event handlers
     */
    dragStarted(event, d) {
        if (!event.active) this.simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    },

    dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    },

    dragEnded(event, d) {
        if (!event.active) this.simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    },

    /**
     * Show node information in the info panel
     */
    showNodeInfo(node) {
        const infoEl = document.getElementById('graph-info');

        if (node.type === 'node') {
            // Find node's publishers and subscribers
            const pubs = this.graphData.edges
                .filter(e => e.source.id === node.id || e.source === node.id)
                .map(e => e.target.id || e.target);
            const subs = this.graphData.edges
                .filter(e => e.target.id === node.id || e.target === node.id)
                .map(e => e.source.id || e.source);

            infoEl.innerHTML = `
                <h4>Node: ${node.label}</h4>
                <div class="node-details">
                    <div>Namespace: ${node.namespace}</div>
                    <div>Publishes: ${pubs.length} topics</div>
                    <div>Subscribes: ${subs.length} topics</div>
                </div>
            `;
        } else {
            infoEl.innerHTML = `
                <h4>Topic: ${node.id}</h4>
                <div class="node-details">
                    <div>Type: ${node.msg_type}</div>
                </div>
            `;
        }
    },

    /**
     * Reset zoom to default
     */
    resetZoom() {
        this.svg.transition()
            .duration(500)
            .call(this.zoom.transform, d3.zoomIdentity);
    },

    /**
     * Handle window resize
     */
    handleResize() {
        const container = document.getElementById('graph-container');
        const width = container.clientWidth;
        const height = container.clientHeight;

        this.svg
            .attr('width', width)
            .attr('height', height);

        if (this.simulation) {
            this.simulation.force('center', d3.forceCenter(width / 2, height / 2));
            this.simulation.alpha(0.3).restart();
        }
    },

    /**
     * Start auto-refresh
     */
    startAutoRefresh() {
        this.stopAutoRefresh();
        this.autoRefreshInterval = setInterval(() => {
            this.loadGraph();
        }, 5000);
    },

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }
};
