import {expect, it, vi} from 'vitest';
import {CatalogUpdates} from './catalogUpdates';
import type {Catalog} from './types';

it('keeps a saved operator visible when an older catalog response finishes late', async () => {
  const updates = new CatalogUpdates();
  const oldCatalog: Catalog = {schema_version: 1, operators: []};
  const published = {...oldCatalog, operators: [{id: 'lab.saved', category: 'data'}]} as Catalog;
  let visible = oldCatalog;
  const render = vi.fn((catalog: Catalog) => {visible = catalog;});
  let complete!: (value: Catalog) => void;
  const pending = new Promise<Catalog>(resolve => {complete = resolve;});
  const checkpoint = updates.checkpoint();
  const poll = pending.then(catalog => updates.apply(catalog, render, checkpoint));
  updates.apply(published, render);
  complete(oldCatalog);
  expect(await poll).toBe(false);
  expect(visible.operators.map(operator => operator.id)).toEqual(['lab.saved']);
  expect(render).toHaveBeenCalledTimes(1);
  const next = updates.checkpoint();
  expect(updates.apply({...oldCatalog}, render, next)).toBe(true);
  expect(visible.operators).toEqual([]);
});
