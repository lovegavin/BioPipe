import { describe, expect, it } from 'vitest';
import { inputAccept, renameSourceDimensions } from './readerInput';
import type { Catalog } from './types';

describe('registry-based input file filters', () => {
  it('includes companions and only supported compression variants', () => {
    const catalog: Catalog = {schema_version:1, operators:[], readers:[
      {name:'CsvReader', extensions:['.csv'], output_contract:null},
      {name:'Plink1Reader', extensions:['.bed'], requires_siblings:['.bim','.fam'], handles_compression:true, output_contract:null},
      {name:'MtxReader', extensions:['.mtx'], handles_compression:true, output_contract:null,
        file_input:{compression:['.gz'], companions:[['barcodes.tsv','barcodes.tsv.gz']]}},
    ]};
    const values = inputAccept(catalog).split(',');
    expect(values).toEqual(expect.arrayContaining(['.csv','.csv.gz','.csv.bz2','.csv.xz','.bed','.bim','.fam','.mtx.gz','.tsv.gz']));
    expect(values).not.toContain('.bed.gz');
    expect(values).not.toContain('.csv.zst');
  });
  it('accepts newly registered formats without a frontend extension table', () => {
    expect(inputAccept({schema_version:1, operators:[], readers:[{name:'LabReader',extensions:['.lab'],handles_compression:true,output_contract:null}]})).toBe('.lab');
  });
});

describe('dimension editing', () => {
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
