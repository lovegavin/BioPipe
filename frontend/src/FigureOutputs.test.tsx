import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import {FigureLinks, figureFormats} from './FigureOutputs';
import {groupParameters} from './execution';

describe('saved publication figures', () => {
  it('opens saved formats directly, without a download action or a new rendering request', () => {
    const html = renderToStaticMarkup(<FigureLinks jobId="ssh:server:run" step={3} formats={['png','pdf','svg']}/>);
    for (const format of ['png','pdf','svg']) {
      expect(html).toContain(`打开 ${format.toUpperCase()}`);
      expect(html).toContain(`/exports/3/figure?format=${format}`);
    }
    expect(html).toContain('target="_blank"');
    expect(html).not.toContain('download');
  });
  it('shows only recorded formats and supports old enrichment and PDF reports', () => {
    expect(figureFormats({figures:[{format:'svg'},{format:'png'},{format:'pdf'},{format:'exe'}]})).toEqual(['png','pdf','svg']);
    expect(figureFormats({figure_path:'/run/old.png'})).toEqual(['png']);
    expect(figureFormats({path:'output\\plot.pdf'})).toEqual(['pdf']);
    expect(figureFormats({path:'/run/table.json'})).toEqual([]);
  });
  it('keeps figure sizing and resolution in the collapsed advanced parameters', () => {
    const groups = groupParameters([{key:'figure_dpi',label:'DPI',type:'integer'}]);
    expect(groups[0].id).toBe('advanced');
  });
});
