import { describe, expect, it } from 'vitest';
import { inputAccept, readerForPath, renameSourceDimensions, rePointSource } from './readerInput';
import type { Catalog } from './types';

describe('registry-based input file filters', () => {
  it('includes companions and only supported compression variants', () => {
    const catalog: Catalog = {schema_version:1, operators:[], readers:[
      {id:'CsvReader', extensions:['.csv'], contracts:{output:null}},
      {id:'Plink1Reader', extensions:['.bed'], requires_siblings:['.bim','.fam'], handles_compression:true, contracts:{output:null}},
      {id:'MtxReader', extensions:['.mtx'], handles_compression:true, contracts:{output:null},
        file_input:{compression:['.gz'], companions:[['barcodes.tsv','barcodes.tsv.gz']]}},
    ]};
    const values = inputAccept(catalog).split(',');
    expect(values).toEqual(expect.arrayContaining(['.csv','.csv.gz','.csv.bz2','.csv.xz','.bed','.bim','.fam','.mtx.gz','.tsv.gz']));
    expect(values).not.toContain('.bed.gz');
    expect(values).not.toContain('.csv.zst');
  });
  it('accepts newly registered formats without a frontend extension table', () => {
    expect(inputAccept({schema_version:1, operators:[], readers:[{id:'LabReader',extensions:['.lab'],handles_compression:true,contracts:{output:null}}]})).toBe('.lab');
  });
  it('uses the same declared compression rules for selection and the inspector', () => {
    const catalog: Catalog = {schema_version:1, operators:[], readers:[
      {id:'GafReader', extensions:['.gaf'], handles_compression:true, contracts:{output:null},
        file_input:{compression:['.gz']}},
      {id:'H5adReader', extensions:['.h5ad'], handles_compression:false, contracts:{output:null}},
    ]};
    expect(inputAccept(catalog)).toContain('.gaf.gz');
    expect(readerForPath(catalog, 'INPUT.GAF.GZ')?.id).toBe('GafReader');
    expect(readerForPath(catalog, 'input.gaf.xz')).toBeUndefined();
    expect(readerForPath(catalog, 'input.h5ad.xz')?.id).toBe('H5adReader');
    expect(readerForPath(catalog, 'input.h5ad.zst')).toBeUndefined();
  });
});

describe('dimension editing', () => {
  it('retains same-reader settings but replaces location and paired file paths', () => {
    const catalog: Catalog = {schema_version: 1, operators: [], readers: [
      {id:'FastqReader', extensions:['.fastq'], contracts:{output:null}, parameters:[{key:'mate_path', label:'Mate', type:'string', path_kind:'source'}]},
      {id:'CSVReader', extensions:['.csv'], contracts:{output:null}},
    ]};
    const previous = {path:'old.fastq.gz', dims:['custom'], labels:{custom:'auto'}, args:{mate_path:'/server/old_R2.fastq', sample:'A'}, location:{kind:'ssh' as const, profile_id:'server'}};
    const uploaded = {path:'new.fastq.gz', dims:['file'], labels:{}, args:{mate_path:'new_R2.fastq.gz'}};
    const next = rePointSource(previous, uploaded, catalog);
    expect(next.location).toEqual({kind:'local'});
    expect(next.dims).toEqual(['custom']);
    expect(next.args).toEqual({sample:'A',mate_path:'new_R2.fastq.gz'});
    expect(rePointSource(previous, {...uploaded,args:{}}, catalog).args).toEqual({sample:'A'});
    expect(rePointSource(previous, {...uploaded,path:'new.csv',args:{}}, catalog).dims).toEqual(['file']);
    expect(previous.args.mate_path).toBe('/server/old_R2.fastq');
  });
  it('renames labels and cross-axis rules together without mutating the original', () => {
    const source = {path:'x.csv', dims:['sample','feature'], labels:{sample:{feature:0}, feature:'builtin'}, args:{}};
    expect(renameSourceDimensions(source, ['cell','gene']).labels).toEqual({cell:{gene:0},gene:'builtin'});
    expect(source.labels).toEqual({sample:{feature:0},feature:'builtin'});
    expect(renameSourceDimensions(source, ['feature','sample']).labels).toEqual({feature:{sample:0},sample:'builtin'});
  });
  it('rejects duplicate names and supports adding and removing dimensions', () => {
    const source = {path:'x',dims:['a','b'],labels:{a:'auto',b:'builtin'},args:{}};
    expect(() => renameSourceDimensions(source,['x','x'])).toThrow();
    expect(renameSourceDimensions(source,['x']).labels).toEqual({x:'auto'});
    expect(renameSourceDimensions(source,['x','y','z']).labels).toEqual({x:'auto',y:'builtin',z:'auto'});
  });
});
