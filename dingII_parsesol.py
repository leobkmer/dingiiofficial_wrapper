from dingII.dingII_util import *
from dingII.ilp_util_adj import *
import sys
import logging


def set_edges(rd, vrs):
    for eid, val in vrs['x'].items():
        u,v,k = tuple([int(s) for s in eid.strip().split('_')])
        if val == 1:
            rd[u][v][k]['selected'] = True
        else:
            rd[u][v][k]['selected'] = False

DELETION = 'x'
def get_matching(rd):
    #record number of occs seen per family
    genes_seen = {}
    match ={}
    #print(rd.edges(data=True))
    for u,v, d in rd.edges(data=True):
        if u in match or v in match:
            continue
        if not d['etype'] == SELFEDGE:
            continue
        u_ = [partner for partner, edges in rd[u].items() for e, edgedata in edges.items() if edgedata['selected'] and edgedata['etype']!= ADJACENCY]
        v_ = [partner for partner, edges in rd[v].items() for e, edgedata in edges.items() if edgedata['selected'] and edgedata['etype']!= ADJACENCY]
        if len(u_) != 1:
            LOG.fatal('Vertex %i has not degree 2!'%u)
            sys.exit(1)
        if len(v_) != 1:
            LOG.fatal('Vertex %i has not degree 2!'%v)
            sys.exit(1)
        u_ = u_[0]
        v_ = v_[0]
        if u_ == v:
            match[u] = DELETION
            match[v] = DELETION
        else:
            gene = rd.nodes[u]['gene']
            dadd(genes_seen, gene,1)
            matchid = dgetc(genes_seen,gene)
            match[u] = matchid
            match[v] = matchid
            match[v_] = matchid
            match[u_] = matchid
    return match
            
def relabel(extremitygenomes, gnmnames, match):
    gnms = []
    for name, e_gnm in zip(gnmnames, extremitygenomes):
        gnm = []
        for e_chrm in e_gnm:
            chrm = []
            chr_type = CHR_CIRCULAR
            if e_chrm[0][1] == TELOGENE:
                e_chrm_ = e_chrm[1:len(e_chrm)-1]
                chr_type = CHR_LINEAR
            else:
                e_chrm_ = e_chrm
            for i in range(1, len(e_chrm_),2):
                eid1 ,g, e  = e_chrm_[i-1]
                eid2 ,_, _  = e_chrm_[i]
                m1 = match[eid1]
                m2 = match[eid2]
                if not m1 == m2:
                    LOG.fatal('Doubly matched gene {} with indices {} and {}'.format(g,m1,m2))
                    sys.exit(1)
                orient = ORIENT_POSITIVE
                if e == EXTREMITY_HEAD:
                    orient = ORIENT_NEGATIVE
                chrm.append((orient,'{}_{}'.format(g, m1)))
            gnm.append((chr_type,chrm))
        gnms.append((name,gnm))
    return gnms

def print_genomes(genomes, file=sys.stdout):
    for name, chrs in genomes:
        print('>%s'%name, file=file)
        for c_type, chrm in chrs:
            for g in chrm:
                print('%s%s '%(g), end='', file=file)
            print('%s'%c_type, file=file)
        print('', file=file)

def get_runs(rd):
    rd_ = rd.copy()
    nonselected = [(u,v,k) for u,v,k in rd_.edges if not rd_.get_edge_data(u, v, key=k)['selected']]
    rd_.remove_edges_from(nonselected)
    ext_to_orient = lambda xt: ORIENT_POSITIVE if xt==EXTREMITY_TAIL else ORIENT_NEGATIVE
    cycle_runs = []
    for cyc in [rd_.subgraph(c).copy() for c in nx.connected_components(rd_)]:
        runs = []
        genome = None
        run = []
        for u,v,k in nx.eulerian_circuit(cyc, keys=True):
            data = rd_.get_edge_data(u,v,key=k)
            if data['etype'] == SELFEDGE:
                gnm_u = cyc.nodes[u]['genome']
                if gnm_u != genome:
                    if genome != None:
                        runs.append((genome, run))
                    genome = gnm_u
                    run=[]
                run.append((ext_to_orient(cyc.nodes[u]['extremity']),cyc.nodes[u]['gene']))
        if len(runs) > 0:
            #if the last run has the same genome as the first,they are actually the same run
            if runs[0][0] == genome:
                run.extend(runs[0][1])
                runs[0] = (genome, run)
            elif genome != None:
                runs.append((genome, run))
        elif genome != None:
                runs.append((genome, run))
        if len(runs) > 0:
            cycle_runs.append(runs)
    return cycle_runs
            
def small_lambda(c):
    n_runs = len(c)
    if n_runs ==0:
        return 0
    elif n_runs ==1:
        return 1
    else:
        return n_runs//2 +1

def canonize(cyc):
    '''
    Make every cycle start with a (possibly empty) A-run
    '''
    if cyc[0][0] == GENOME1:
        return cyc
    elif len(cyc) <= 1:
        cyc_=[(GENOME1,[])]+cyc
        return cyc_
    else:
        fst = cyc[0]
        cyc_ = cyc[1::]
        cyc_.append(fst)
        return cyc_

def print_runs(runs, file=sys.stdout):
    for cyc in runs:
        cyc = canonize(cyc)
        print('\t'.join([''.join(['%s%s'%kv for kv in r[1]]) for r in cyc]), file=file)


def main(args):
    obj, vrs = read_gurobi(args.solgur)
    genomes = read_genomes(args)
    print('d(%s,%s) = %i'%(genomes[0][0], genomes[1][0], obj))
    rd, _ , _, _, extr_genomes = full_relational_diagram(genomes, logging)
    set_edges(rd, vrs)
    if args.runs or args.numindels:
        runs = get_runs(rd)
        if args.numindels:
            print('sum(lambda(C)) = %i'%sum([small_lambda(c) for c in runs]))
        if args.runs:
            print_runs(runs,file=args.runs)
    if args.matching:
        m = get_matching(rd)
        matched_gnms = relabel(extr_genomes, [gnm[0] for gnm in genomes] , m)
        print_genomes(matched_gnms, file=args.matching)
